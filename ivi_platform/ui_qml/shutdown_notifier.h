#pragma once

#include <QByteArray>
#include <QtGlobal>
#include <stdexcept>
#ifdef __linux__
#include <fcntl.h>
#include <sys/socket.h>
#include <unistd.h>
#endif

// Private local desktop-supervisor channel; carries no CAN data or keys.
// Notify before teardown can wait on a worker. The owner enforces the deadline.
class ShutdownNotifier {
public:
    ShutdownNotifier() {
        const auto value=qgetenv("IVI_SHUTDOWN_NOTIFY_FD");
        if(value.isEmpty())return;
#ifdef __linux__
        bool ok=false;const int fd=value.toInt(&ok);
        int kind=0;socklen_t length=sizeof(kind);
        const int flags=fd>=3 ? ::fcntl(fd,F_GETFD) : -1;
        if(!ok || flags<0 || ::getsockopt(fd,SOL_SOCKET,SO_TYPE,&kind,&length)!=0 ||
           kind!=SOCK_STREAM || ::fcntl(fd,F_SETFD,flags|FD_CLOEXEC)<0)
            throw std::invalid_argument("invalid desktop shutdown channel");
        descriptor_=fd;
#else
        throw std::invalid_argument("desktop shutdown channel requires Linux");
#endif
    }
    ShutdownNotifier(const ShutdownNotifier&)=delete;
    ShutdownNotifier& operator=(const ShutdownNotifier&)=delete;
    ~ShutdownNotifier() {
        notify();
#ifdef __linux__
        if(descriptor_>=0)::close(descriptor_);
#endif
    }
    void notify() noexcept {
#ifdef __linux__
        if(descriptor_<0 || notified_)return;
        notified_=true;
        const char notice='Q';
        (void)::send(descriptor_,&notice,1,MSG_NOSIGNAL|MSG_DONTWAIT);
#endif
    }
private:
    int descriptor_=-1;
    bool notified_=false;
};
