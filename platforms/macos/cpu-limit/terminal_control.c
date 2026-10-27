/* Local macOS backend for cpulimit 0.2, GPL-2.0-or-later.
 * Uses cpulimit's SIGSTOP/SIGCONT technique with a shared token budget,
 * recursive terminal ancestry, PID identities and a recovery watchdog.
 */
#include <errno.h>
#include <getopt.h>
#include <libproc.h>
#include <mach/mach_time.h>
#include <poll.h>
#include <signal.h>
#include <stdatomic.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <sys/file.h>
#include <sys/mman.h>
#include <sys/proc.h>
#include <sys/sysctl.h>
#include <sys/wait.h>
#include <time.h>
#include <unistd.h>

#define MAX_PROCS 16384
typedef struct {
    pid_t pid, ppid;
    uint64_t birth, cpu;
    int member, selected;
    char name[64];
} Entry;
typedef struct {
    pid_t pid;
    uint64_t birth;
    _Atomic int active;
} Paused;
static Paused *paused;
static volatile sig_atomic_t quitting;
static int wake_pipe[2];
static double cpu_tick_seconds;

static double now(void) {
    struct timespec ts;
    clock_gettime(CLOCK_MONOTONIC, &ts);
    return ts.tv_sec + ts.tv_nsec / 1e9;
}
static void nap(double seconds) {
    struct timespec ts = {(time_t)seconds, (long)((seconds - (time_t)seconds) * 1e9)};
    while (!quitting && nanosleep(&ts, &ts) && errno == EINTR) {}
}
static void on_signal(int signo) { (void)signo; quitting = 1; }
static uint64_t birth(const struct proc_bsdinfo *b) {
    return (uint64_t)b->pbi_start_tvsec * 1000000 + b->pbi_start_tvusec;
}
static int info(pid_t pid, struct proc_bsdinfo *b) {
    return proc_pidinfo(pid, PROC_PIDTBSDINFO, 0, b, sizeof(*b)) == sizeof(*b);
}
static void resume_all(void) {
    for (int i = 0; i < MAX_PROCS; ++i) {
        if (!atomic_load(&paused[i].active)) continue;
        struct proc_bsdinfo b;
        if (info(paused[i].pid, &b) && birth(&b) == paused[i].birth)
            kill(paused[i].pid, SIGCONT);
        atomic_store(&paused[i].active, 0);
    }
}
static void pause_jobs(Entry *list, int count) {
    int slot = 0;
    for (int i = 0; i < count && !quitting; ++i) {
        if (!list[i].selected) continue;
        struct proc_bsdinfo b;
        if (!info(list[i].pid, &b) || birth(&b) != list[i].birth ||
            b.pbi_status == SSTOP || b.pbi_status == SZOMB) continue;
        paused[slot].pid = list[i].pid;
        paused[slot].birth = list[i].birth;
        atomic_store(&paused[slot].active, 1);
        if (kill(list[i].pid, SIGSTOP)) atomic_store(&paused[slot].active, 0);
        ++slot;
    }
}
static pid_t start_watchdog(int lock_fd) {
    paused = mmap(NULL, sizeof(*paused) * MAX_PROCS, PROT_READ | PROT_WRITE,
                  MAP_SHARED | MAP_ANON, -1, 0);
    if (paused == MAP_FAILED || pipe(wake_pipe)) { perror("watchdog setup"); exit(1); }
    pid_t owner = getpid();
    pid_t child = fork();
    if (child < 0) { perror("fork watchdog"); exit(1); }
    if (!child) {
        close(wake_pipe[1]);
        if (lock_fd >= 0) close(lock_fd);
        struct pollfd fd = {.fd = wake_pipe[0], .events = POLLIN | POLLHUP};
        while (!quitting) {
            int result = poll(&fd, 1, 5000);
            if (result < 0 && errno == EINTR) continue;
            if (result <= 0) {
                /* A wedged controller must not leave jobs suspended. */
                if (getppid() == owner) kill(owner, SIGKILL);
                break;
            }
            char buffer[256];
            if (read(wake_pipe[0], buffer, sizeof(buffer)) <= 0) break;
        }
        resume_all();
        _exit(0);
    }
    close(wake_pipe[0]);
    return child;
}
static int compare(const void *a, const void *b) {
    pid_t x = ((const Entry *)a)->pid, y = ((const Entry *)b)->pid;
    return (x > y) - (x < y);
}
static Entry *lookup(Entry *list, int count, pid_t pid) {
    Entry key = {.pid = pid};
    return bsearch(&key, list, count, sizeof(*list), compare);
}
static int agent(const char *name, pid_t pid) {
    if (!strcmp(name, "codex") || !strcmp(name, "claude") ||
        !strcmp(name, "Codex") || !strcmp(name, "Claude")) return 1;
    /* Claude's native executable is named after its version (e.g. 2.1.310). */
    if (name[0] >= '0' && name[0] <= '9') {
        char path[PROC_PIDPATHINFO_MAXSIZE];
        if (proc_pidpath(pid, path, sizeof(path)) > 0 && strstr(path, "/claude/versions/")) return 1;
    }
    return 0;
}
static int frontend(const char *name, pid_t pid) {
    if (agent(name, pid)) return 1;
    const char *names[] = {"tmux", "zsh", "bash", "sh", "fish", "login", "claude",
        "codex", "cpulimit", "cpulimit-terminal", "vim", "nvim", "vi", "nano",
        "less", "more", "top", "htop", "ssh", "mosh-client", "mosh-server",
        "telnet", "screen", "dtach", NULL};
    for (int i = 0; names[i]; ++i) if (!strcmp(name, names[i])) return 1;
    if (!strncmp(name, "iTerm", 5) || !strncmp(name, "tmux-", 5) ||
        !strncmp(name, "codex-code-mode", 15) ||
        !strncmp(name, "Claude Helper", 13) || !strncmp(name, "Codex Helper", 12)) return 1;
    return 0;
}
static int terminal(const char *name, pid_t pid) {
    return !strcmp(name, "tmux") || !strcmp(name, "iTerm2") ||
           !strncmp(name, "iTermServer", 11) || agent(name, pid);
}
static int snapshot(Entry *list, Entry *previous, int previous_count,
                    pid_t target, uint64_t target_birth, int terminals,
                    int children, pid_t watchdog) {
    pid_t pids[MAX_PROCS];
    int bytes = proc_listpids(PROC_UID_ONLY, getuid(), pids, sizeof(pids));
    if (bytes <= 0 || bytes >= (int)sizeof(pids)) return -1;
    int count = 0;
    for (int i = 0; i < bytes / (int)sizeof(pid_t); ++i) {
        struct proc_taskallinfo t;
        if (pids[i] <= 1 || pids[i] == getpid() || pids[i] == watchdog) continue;
        if (proc_pidinfo(pids[i], PROC_PIDTASKALLINFO, 0, &t, sizeof(t)) != sizeof(t)) continue;
        if (t.pbsd.pbi_uid != getuid() || t.pbsd.pbi_status == SZOMB) continue;
        Entry *e = &list[count++];
        memset(e, 0, sizeof(*e));
        e->pid = pids[i]; e->ppid = t.pbsd.pbi_ppid; e->birth = birth(&t.pbsd);
        e->cpu = t.ptinfo.pti_total_user + t.ptinfo.pti_total_system;
        snprintf(e->name, sizeof(e->name), "%s", t.pbsd.pbi_name[0] ? t.pbsd.pbi_name : t.pbsd.pbi_comm);
        Entry *old = lookup(previous, previous_count, e->pid);
        e->member = (old && old->birth == e->birth && old->member) ||
            (terminals ? terminal(e->name, e->pid) : (e->pid == target && e->birth == target_birth));
    }
    qsort(list, count, sizeof(*list), compare);
    if (children || terminals) {
        int changed;
        do {
            changed = 0;
            for (int i = 0; i < count; ++i) {
                if (list[i].member) continue;
                Entry *parent = lookup(list, count, list[i].ppid);
                if (parent && parent->member) { list[i].member = 1; changed = 1; }
            }
        } while (changed);
    }
    for (int i = 0; i < count; ++i)
        list[i].selected = list[i].member && (!terminals || !frontend(list[i].name, list[i].pid));
    return count;
}
static void save_status(const char *path, int cap, double cpu, int jobs, pid_t watchdog) {
    if (!path) return;
    char temporary[4096];
    if (snprintf(temporary, sizeof(temporary), "%s.tmp", path) >= (int)sizeof(temporary)) return;
    FILE *out = fopen(temporary, "w");
    if (!out) return;
    fprintf(out, "{\"scope\":\"terminal-and-agent-jobs-v2\",\"pid\":%d,\"watchdog_pid\":%d,\"cap_percent\":%d,"
            "\"measured_percent\":%.1f,\"jobs\":%d,\"updated\":%lld}\n",
            getpid(), watchdog, cap, cpu, jobs, (long long)time(NULL));
    if (fclose(out) == 0) rename(temporary, path);
}
int terminal_main(int argc, char **argv) {
    mach_timebase_info_data_t timebase;
    if (mach_timebase_info(&timebase) != KERN_SUCCESS || !timebase.denom) return 1;
    cpu_tick_seconds = (double)timebase.numer / timebase.denom / 1e9;
    int cap = 0, terminals = 0, children = 0, list_only = 0, verbose = 0;
    pid_t target = 0;
    const char *status_file = NULL, *lock_file = NULL;
    const struct option options[] = {
        {"terminal-jobs", no_argument, NULL, 'T'}, {"pid", required_argument, NULL, 'p'},
        {"limit", required_argument, NULL, 'l'}, {"include-children", no_argument, NULL, 'i'},
        {"list", no_argument, NULL, 'L'}, {"verbose", no_argument, NULL, 'v'},
        {"status-file", required_argument, NULL, 's'}, {"lock-file", required_argument, NULL, 'k'},
        {"help", no_argument, NULL, 'h'}, {0, 0, 0, 0}};
    int opt;
    while ((opt = getopt_long(argc, argv, "Tip:l:Lvs:k:h", options, NULL)) != -1) {
        char *end = NULL;
        long value;
        switch (opt) {
        case 'T': terminals = 1; break;
        case 'i': children = 1; break;
        case 'L': list_only = 1; break;
        case 'v': verbose = 1; break;
        case 's': status_file = optarg; break;
        case 'k': lock_file = optarg; break;
        case 'p': case 'l':
            errno = 0; value = strtol(optarg, &end, 10);
            if (errno || !*optarg || *end || value <= 0 || value > 1000000) return 2;
            if (opt == 'p') target = (pid_t)value; else cap = (int)value;
            break;
        default:
            puts("cpulimit-terminal: local macOS build of cpulimit 0.2\n"
                 "  --terminal-jobs -l 400 [--status-file PATH] [--lock-file PATH]\n"
                 "  -p PID [-i] -l PERCENT\n  --terminal-jobs --list\n"
                 "100% = one core's CPU time. This is an average budget, not CPU affinity.");
            return opt == 'h' ? 0 : 2;
        }
    }
    if (optind != argc || terminals == (target != 0) || target == 1 ||
        (!list_only && (cap < 1 || cap > 100 * sysconf(_SC_NPROCESSORS_ONLN)))) {
        fputs("Specify --terminal-jobs or -p PID, and a valid -l CPU percentage.\n", stderr);
        return 2;
    }
    uint64_t target_birth = 0;
    if (target) {
        struct proc_bsdinfo b;
        if (!info(target, &b) || b.pbi_uid != getuid() || target == getpid()) return 2;
        target_birth = birth(&b);
    }
    Entry *current = calloc(MAX_PROCS, sizeof(*current));
    Entry *previous = calloc(MAX_PROCS, sizeof(*previous));
    if (!current || !previous) return 1;
    int previous_count = 0;
    if (list_only) {
        int count = snapshot(current, previous, 0, target, target_birth, terminals, children, -1);
        if (count < 0) return 1;
        puts("PID     PPID    ACTION   PROCESS");
        for (int i = 0; i < count; ++i) if (current[i].member)
            printf("%-7d %-7d %-8s %s\n", current[i].pid, current[i].ppid,
                   current[i].selected ? "limit" : "exempt", current[i].name);
        return 0;
    }
    int lock_fd = -1;
    if (lock_file) {
        lock_fd = open(lock_file, O_CREAT | O_RDWR, 0600);
        if (lock_fd < 0 || flock(lock_fd, LOCK_EX | LOCK_NB)) {
            fputs("Another terminal limiter is already running, or lock unavailable.\n", stderr);
            return 1;
        }
    }
    struct sigaction action = {.sa_handler = on_signal};
    sigemptyset(&action.sa_mask);
    sigaction(SIGTERM, &action, NULL); sigaction(SIGINT, &action, NULL);
    sigaction(SIGHUP, &action, NULL); signal(SIGPIPE, SIG_IGN);
    pid_t watchdog = start_watchdog(lock_fd);
    double budget = cap / 100.0, credit = 0, last = now();
    double report_time = last, report_cpu = 0;
    int exit_code = 0;
    printf("CPU cap active: %d%% shared; controller=%d watchdog=%d\n", cap, getpid(), watchdog);
    fflush(stdout);
    while (!quitting) {
        if (write(wake_pipe[1], ".", 1) != 1 || waitpid(watchdog, NULL, WNOHANG) != 0) {
            exit_code = 1; break;
        }
        int count = snapshot(current, previous, previous_count, target, target_birth,
                             terminals, children, watchdog);
        if (count < 0) { exit_code = 1; break; }
        double stamp = now(), spent = 0;
        int jobs = 0, members = 0;
        for (int i = 0; i < count; ++i) {
            if (current[i].member) ++members;
            if (!current[i].selected) continue;
            ++jobs;
            Entry *old = lookup(previous, previous_count, current[i].pid);
            if (old && old->birth == current[i].birth && current[i].cpu >= old->cpu)
                spent += (current[i].cpu - old->cpu) * cpu_tick_seconds;
        }
        double elapsed = stamp - last;
        last = stamp;
        credit += budget * elapsed - spent;
        if (credit > budget * 0.05) credit = budget * 0.05;
        /* Sleep/wake should not accumulate an obsolete throttling debt. */
        if (elapsed > 2) credit = 0;
        report_cpu += spent;
        if (stamp - report_time >= 2 || previous_count == 0) {
            double measured = 100 * report_cpu / (stamp - report_time + 1e-9);
            save_status(status_file, cap, measured, jobs, watchdog);
            if (verbose) { printf("%.1f%% CPU, %d jobs\n", measured, jobs); fflush(stdout); }
            report_cpu = 0; report_time = stamp;
        }
        if (!terminals && members == 0) break;
        if (credit < 0 && jobs) {
            double pause_until = now() - credit / budget;
            pause_jobs(current, count);
            while (!quitting && now() < pause_until) {
                double remaining = pause_until - now();
                nap(remaining > 0.1 ? 0.1 : remaining);
                if (write(wake_pipe[1], ".", 1) != 1) { quitting = 1; exit_code = 1; }
            }
            resume_all();
        }
        Entry *swap = previous; previous = current; current = swap;
        previous_count = count;
        nap(0.05);
    }
    resume_all();
    close(wake_pipe[1]);
    while (waitpid(watchdog, NULL, 0) < 0 && errno == EINTR) {}
    if (status_file) unlink(status_file);
    if (lock_fd >= 0) close(lock_fd);
    free(current); free(previous);
    return exit_code;
}
