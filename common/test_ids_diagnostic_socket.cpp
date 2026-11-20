#include "ids_diagnostic_socket.h"
#include "ids_submission_order.h"
#include <iostream>
#include <fstream>
#include <sys/wait.h>
using namespace capstone::session_v2;
void check(bool value,const char* reason){if(!value)throw std::runtime_error(reason);}
int main(){
    char directory[]="/tmp/cid-test-XXXXXX";
    if(!mkdtemp(directory))return 1;
    const std::string path=std::string(directory)+"/ids.sock";
    try{
        std::vector<std::uint8_t> body(52);body[6]=0x40;body[8]=0x80;
        body[16]=1;body[23]=1;body[34]=3;body[35]=0xe8;
        body[39]=20;body[46]=3;body[47]=0xe8;body[50]=3;
        std::vector<std::uint8_t> packet{'C','I','D','2',7,52,0,0,0,0,0,0,3,232};
        packet.insert(packet.end(),body.begin(),body.end());
        IdsSubmissionOrder order;
        const IdsDiagnosticSubmission observation{DiagnosticKind::Observation,body};
        check(order.accept(observation,100),"first observation rejected");
        check(!order.accept(observation,101),"duplicate tick accepted");
        auto next=observation;next.body[23]=2;
        check(!order.accept(next,99),"backward local time accepted");
        check(order.accept(next,102),"next observation rejected");
        next.body[0]=1;next.body[23]=3;
        check(!order.accept(next,103),"foreign source accepted");
        {
            IdsSubmissionOrder incidents;
            auto heartbeat=observation;heartbeat.body[48]=1;
            check(incidents.accept(heartbeat,0),"incident heartbeat");
            std::vector<std::uint8_t> value(104);
            std::copy_n(body.begin(),16,value.begin());value[22]=0x40;value[24]=0x80;
            value[32]=1;value[33]=1;value[35]=3;value[39]=1;value[43]=1;
            value[46]=3;value[47]=0xe8;value[51]=20;value[56]=value[57]=0xff;
            IdsDiagnosticSubmission incident{DiagnosticKind::IncidentStatus,value};
            check(incidents.accept(incident,1),"first incident");
            heartbeat.body[23]=2;check(incidents.accept(heartbeat,1000),"next heartbeat");
            incident.body[43]=2;
            check(!incidents.accept(incident,1001),"stale incident revision");
            incident.body[39]=2;check(incidents.accept(incident,1001),"new revision");
            heartbeat.body[23]=3;heartbeat.body[48]=0;heartbeat.body[46]=0x13;heartbeat.body[47]=0x88;
            check(incidents.accept(heartbeat,2000),"quiet heartbeat");
            incident.body[43]=3;incident.body[39]=3;incident.body[33]=2;
            incident.body[54]=0x13;incident.body[55]=0x88;
            check(incidents.accept(incident,2001),"confirmed end");
            heartbeat.body[23]=4;heartbeat.body[48]=1;check(incidents.accept(heartbeat,3000),"new active heartbeat");
            incident.body[43]=4;incident.body[39]=4;incident.body[33]=1;incident.body[54]=incident.body[55]=0;
            check(!incidents.accept(incident,3001),"ended incident resurrected");
            incident.body[16]=1;incident.body[39]=1;
            check(incidents.accept(incident,3001),"new incident after end");
        }
        int sender=socket(AF_UNIX,SOCK_DGRAM|SOCK_CLOEXEC,0);check(sender>=0,"sender");
        sockaddr_un address{};address.sun_family=AF_UNIX;strcpy(address.sun_path,path.c_str());
        auto send=[&](const std::vector<std::uint8_t>& bytes){check(sendto(sender,bytes.data(),bytes.size(),0,
            reinterpret_cast<sockaddr*>(&address),sizeof(address))==static_cast<ssize_t>(bytes.size()),"send");};
        {
            IdsDiagnosticSocket first(path,getuid(),getpid());
            send(packet);check(!first.receive(4000),"first queued stale observation accepted");
            send(packet);check(first.receive(1000).has_value(),"fresh observation after stale first rejected");
        }
        {
            IdsDiagnosticSocket receiver(path,getuid(),getpid());
            check(!receiver.receive(1000),"empty socket blocked/returned data");
            bool refused=false;try{IdsDiagnosticSocket duplicate(path,getuid());}catch(const std::runtime_error&){refused=true;}
            check(refused && access(path.c_str(),F_OK)==0,"existing endpoint overwritten");
            send(packet);const auto accepted=receiver.receive(1000);
            check(accepted && accepted->body==body,"authorized body not received");
            send(packet);check(!receiver.receive(4000),"stale first message accepted");
            send(packet);check(!receiver.receive(999),"future observation accepted");
            send(packet);check(receiver.receive(3999).has_value(),"freshness boundary rejected");
            auto old=packet;old[3]='1';send(old);check(!receiver.receive(1000),"unstamped version accepted");
            send(std::vector<std::uint8_t>(200,0));check(!receiver.receive(1000) && receiver.rejected()==4,"oversize accepted");
            auto bad=packet;bad[0]='X';send(bad);check(!receiver.receive(1000) && receiver.rejected()==5,"invalid body accepted");
        }
        check(access(path.c_str(),F_OK)!=0,"owned socket not removed");
        {
            int gate[2];check(pipe(gate)==0,"lifetime pipe");
            const auto child=fork();check(child>=0,"lifetime fork");
            if(child==0){close(gate[1]);char byte;read(gate[0],&byte,1);_exit(0);}
            close(gate[0]);
            IdsDiagnosticSocket receiver(path,getuid(),child);
            send(packet);check(!receiver.receive(1000) && receiver.rejected()==1,"wrong pid accepted");
            close(gate[1]);int status;check(waitpid(child,&status,0)==child,"lifetime wait");
            send(packet);check(!receiver.receive(1000) && receiver.rejected()==2,"dead owner accepted");
        }
        {
            IdsDiagnosticSocket receiver(path,getuid()+1);
            send(packet);check(!receiver.receive(1000) && receiver.rejected()==1,"wrong uid accepted");
            check(unlink(path.c_str())==0,"test unlink");
            std::ofstream replacement(path);replacement<<"preserve";replacement.close();
        }
        check(access(path.c_str(),F_OK)==0,"replacement path removed");
        close(sender);unlink(path.c_str());rmdir(directory);
        std::cout<<"PASS authorized/rejected credentials, bounded payload, nonblocking, existing and replaced paths\n";
        return 0;
    }catch(const std::exception& error){std::cerr<<error.what()<<'\n';unlink(path.c_str());rmdir(directory);return 1;}
}
