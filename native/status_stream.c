/* An exempt tmux-* frontend: stream a shared cache, never collect host stats. */
#include <errno.h>
#include <signal.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <sys/stat.h>
#include <time.h>
#include <unistd.h>
static volatile sig_atomic_t done;
static void stop(int s) {(void)s;done=1;}
int main(int argc,char **argv) {
    if(argc<2){fputs("Usage: tmux-metrics-status CACHE_FILE [--once]\n",stderr);return 2;}
    int once=argc==3&&!strcmp(argv[2],"--once");
    signal(SIGTERM,stop);signal(SIGINT,stop);
    do {
        struct stat st;FILE *f=NULL;char line[16384];
        if(!stat(argv[1],&st)&&difftime(time(NULL),st.st_mtime)>=0&&difftime(time(NULL),st.st_mtime)<=5)f=fopen(argv[1],"r");
        if(f&&fgets(line,sizeof(line),f))fputs(line,stdout);
        else puts("#[fg=#111827,bg=#facc15] stats unavailable/stale #[default]");
        if(f)fclose(f);fflush(stdout);
        if(!once)usleep(500000);
    }while(!once&&!done);
    return 0;
}
