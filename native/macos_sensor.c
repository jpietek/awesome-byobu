/* Read-only Mach/IOKit sensors. JSON lines form the OS backend interface. */
#include <CoreFoundation/CoreFoundation.h>
#include <IOKit/IOKitLib.h>
#include <mach/mach.h>
#include <mach/processor_info.h>
#include <sys/sysctl.h>
#include <sys/time.h>
#include <net/if.h>
#include <net/if_dl.h>
#include <net/route.h>
#include <ifaddrs.h>
#include <inttypes.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <time.h>
#include <unistd.h>

static char core_kind[256];
static void core_types(void) {
    io_registry_entry_t cpus = IORegistryEntryFromPath(kIOMainPortDefault, "IODeviceTree:/cpus");
    io_iterator_t it;
    if (!cpus) return;
    if (IORegistryEntryGetChildIterator(cpus, kIODeviceTreePlane, &it) == KERN_SUCCESS) {
        io_registry_entry_t cpu;
        while ((cpu = IOIteratorNext(it))) {
            CFTypeRef id = IORegistryEntryCreateCFProperty(cpu, CFSTR("cpu-id"), NULL, 0);
            CFTypeRef type = IORegistryEntryCreateCFProperty(cpu, CFSTR("cluster-type"), NULL, 0);
            uint32_t index = UINT32_MAX; char kind = 0;
            if (id && CFGetTypeID(id) == CFDataGetTypeID() && CFDataGetLength(id) >= 4)
                memcpy(&index, CFDataGetBytePtr(id), 4);
            else if (id && CFGetTypeID(id) == CFNumberGetTypeID())
                CFNumberGetValue(id, kCFNumberSInt32Type, &index);
            if (type && CFGetTypeID(type) == CFDataGetTypeID() && CFDataGetLength(type)) kind = *CFDataGetBytePtr(type);
            else if (type && CFGetTypeID(type) == CFStringGetTypeID()) kind = (char)CFStringGetCharacterAtIndex(type, 0);
            if (index < 256 && (kind == 'E' || kind == 'P')) core_kind[index] = kind;
            if (id) CFRelease(id); if (type) CFRelease(type); IOObjectRelease(cpu);
        }
        IOObjectRelease(it);
    }
    IOObjectRelease(cpus);
}
static int number(CFDictionaryRef d, CFStringRef key, long long *out) {
    CFTypeRef n = CFDictionaryGetValue(d, key);
    return n && CFGetTypeID(n) == CFNumberGetTypeID() && CFNumberGetValue(n, kCFNumberLongLongType, out);
}
static void battery(void) {
    io_service_t svc = IOServiceGetMatchingService(kIOMainPortDefault, IOServiceMatching("AppleSmartBattery"));
    CFMutableDictionaryRef p = NULL;
    if (!svc || IORegistryEntryCreateCFProperties(svc, &p, NULL, 0) != KERN_SUCCESS || !p) {
        printf("null"); if (svc) IOObjectRelease(svc); return;
    }
    long long amp=0, volt=0, cur=0, full=0, pct=0, max_capacity=0;
    int have_amp=number(p,CFSTR("InstantAmperage"),&amp), have_volt=number(p,CFSTR("Voltage"),&volt);
    int plugged=CFDictionaryGetValue(p,CFSTR("ExternalConnected"))==kCFBooleanTrue;
    int charging=CFDictionaryGetValue(p,CFSTR("IsCharging"))==kCFBooleanTrue;
    printf("{\"plugged\":%s,\"status\":\"%s\",\"percent\":",plugged?"true":"false",charging?"Charging":plugged?"Not charging":"Discharging");
    int have_pct=number(p,CFSTR("CurrentCapacity"),&pct);
    int have_max=number(p,CFSTR("MaxCapacity"),&max_capacity);
    if(have_pct&&have_max&&max_capacity>0)printf("%.0f",100.0*pct/max_capacity);
    else if(have_pct&&pct>=0&&pct<=100)printf("%lld",pct);else printf("null");
    printf(",\"power_w\":");if(have_amp&&have_volt)printf("%.6f",llabs(amp)*(double)volt/1e6);else printf("null");
    int have_cur=number(p,CFSTR("AppleRawCurrentCapacity"),&cur);
    int have_full=number(p,CFSTR("AppleRawMaxCapacity"),&full);
    if(!have_cur&&have_pct&&have_max&&max_capacity>100){cur=pct;have_cur=1;}
    if(!have_full&&have_max&&max_capacity>100){full=max_capacity;have_full=1;}
    printf(",\"energy_now_wh\":");if(have_volt&&have_cur)printf("%.6f",cur*(double)volt/1e6);else printf("null");
    printf(",\"energy_full_wh\":");if(have_volt&&have_full)printf("%.6f",full*(double)volt/1e6);else printf("null");
    printf("}"); CFRelease(p); IOObjectRelease(svc);
}
static int sample(host_t host) {
    natural_t ncpu; processor_info_array_t info; mach_msg_type_number_t count;
    if(host_processor_info(host,PROCESSOR_CPU_LOAD_INFO,&ncpu,&info,&count)!=KERN_SUCCESS)return 1;
    printf("{\"platform\":\"macos\",\"cpu\":[");
    for(unsigned i=0;i<ncpu;i++) {
        unsigned *p=(unsigned *)info+i*CPU_STATE_MAX;
        uint64_t busy=(uint64_t)p[CPU_STATE_USER]+p[CPU_STATE_SYSTEM]+p[CPU_STATE_NICE];
        const char *kind=i<256&&core_kind[i]=='E'?"efficiency":i<256&&core_kind[i]=='P'?"performance":"unknown";
        printf("%s{\"id\":%u,\"busy\":%"PRIu64",\"total\":%"PRIu64",\"kind\":\"%s\"}",i?",":"",i,busy,busy+p[CPU_STATE_IDLE],kind);
    }
    vm_deallocate(mach_task_self(),(vm_address_t)info,count*sizeof(integer_t));
    vm_statistics64_data_t vm; count=HOST_VM_INFO64_COUNT; vm_size_t page;
    uint64_t total=0;size_t len=sizeof(total);sysctlbyname("hw.memsize",&total,&len,NULL,0);
    host_page_size(host,&page);
    if(host_statistics64(host,HOST_VM_INFO64,(host_info64_t)&vm,&count)!=KERN_SUCCESS)return 1;
    uint64_t wired=(uint64_t)vm.wire_count*page, comp=(uint64_t)vm.compressor_page_count*page;
    uint64_t app=vm.internal_page_count>vm.purgeable_count?(uint64_t)(vm.internal_page_count-vm.purgeable_count)*page:0;
    uint64_t cached=((uint64_t)vm.external_page_count+vm.purgeable_count)*page;
    int pressure=0;len=sizeof(pressure);int have_pressure=!sysctlbyname("kern.memorystatus_vm_pressure_level",&pressure,&len,NULL,0);
    printf("],\"memory\":{\"total\":%"PRIu64",\"used\":%"PRIu64",\"wired\":%"PRIu64",\"compressed\":%"PRIu64",\"cached\":%"PRIu64",\"pressure\":",total,wired+app+comp,wired,comp,cached);
    if(have_pressure)printf("%d",pressure);else printf("null");printf("},\"network\":{");
    int routes[]={CTL_NET,PF_ROUTE,0,0,NET_RT_IFLIST2,0};size_t route_size=0;int first=1;
    if(!sysctl(routes,6,NULL,&route_size,NULL,0)) {
        char *buffer=malloc(route_size);
        if(buffer&&!sysctl(routes,6,buffer,&route_size,NULL,0)) {
            for(char *p=buffer;p+sizeof(struct if_msghdr)<=buffer+route_size;) {
                struct if_msghdr *base=(void *)p;
                if(!base->ifm_msglen||p+base->ifm_msglen>buffer+route_size)break;
                if(base->ifm_type==RTM_IFINFO2&&base->ifm_msglen>=sizeof(struct if_msghdr2)) {
                    struct if_msghdr2 *msg=(void *)p;char name[IFNAMSIZ];
                    if(!(msg->ifm_flags&IFF_LOOPBACK)&&(msg->ifm_flags&IFF_UP)&&if_indextoname(msg->ifm_index,name)) {
                        printf("%s\"%s\":[%llu,%llu]",first?"":",",name,(unsigned long long)msg->ifm_data.ifi_ibytes,(unsigned long long)msg->ifm_data.ifi_obytes);first=0;
                    }
                }
                p+=base->ifm_msglen;
            }
        }
        free(buffer);
    }
    double load=0;getloadavg(&load,1);
    struct timeval boot={0};len=sizeof(boot);int mib[]={CTL_KERN,KERN_BOOTTIME};sysctl(mib,2,&boot,&len,NULL,0);
    printf("},\"load1\":%.3f,\"uptime_seconds\":%.0f,\"battery\":",load,difftime(time(NULL),boot.tv_sec));
    battery();printf("}\n");fflush(stdout);return 0;
}
int main(int argc,char **argv) {
    double interval=0.5;int once=0;
    for(int i=1;i<argc;i++) {
        if(!strcmp(argv[i],"--once"))once=1;
        else if(!strcmp(argv[i],"--interval")&&i+1<argc)interval=strtod(argv[++i],NULL);
        else return 2;
    }
    if(interval<0.1||interval>60)return 2;
    core_types();host_t host=mach_host_self();
    do {if(sample(host))return 1;if(!once)usleep((useconds_t)(interval*1e6));}while(!once);
    mach_port_deallocate(mach_task_self(),host);return 0;
}
