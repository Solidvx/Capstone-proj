// Linux test-only interposer. Never linked into or installed with the product.
#include <cerrno>
#include <cstdlib>
#include <cstdio>
#include <cstring>
#include <dlfcn.h>
#include <fcntl.h>
#include <unistd.h>

extern "C" int fsync(int fd) {
    char name[64],path[4096];
    const int n=::snprintf(name,sizeof(name),"/proc/self/fd/%d",fd);
    const auto size=n>0 ? ::readlink(name,path,sizeof(path)-1) : -1;
    if(size>=0){
        path[size]='\0';
        if(std::strstr(path,"/stall-event-store/")){
            if(const auto marker=std::getenv("CAPSTONE_STALL_SEEN_FILE")){
                const int output=::open(marker,O_WRONLY|O_CREAT|O_EXCL|O_CLOEXEC,0600);
                if(output>=0){(void)::write(output,"blocked\n",8);::close(output);}
            }
            for(;;)::pause();
        }
    }
    using Sync=int(*)(int);
    static const auto original=reinterpret_cast<Sync>(::dlsym(RTLD_NEXT,"fsync"));
    if(!original){errno=EIO;return -1;}
    return original(fd);
}
