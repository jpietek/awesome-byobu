// Per-core CPU sparkline for the Byobu status bar. One host_processor_info
// call per tick, no forks. P-cores first, then E-cores, separated by a space.
// Usage: tmux-cpuspark [--watch SECONDS]  fractional ok, e.g. 0.5 (no --watch: one 1s sample)
#include <mach/mach.h>
#include <mach/processor_info.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <unistd.h>
#include <sys/sysctl.h>

static const char *glyph[] = {"▁","▂","▃","▄","▅","▆","▇","█"};
// Cool-to-hot rainbow by load level, drawn on the bar's own background.
static const char *color[] = {"#38bdf8","#22d3ee","#4ade80","#a3e635","#facc15","#fb923c","#f87171","#ef4444"};

static int sample(natural_t *ncpu, unsigned int **ticks) {
    processor_info_array_t info; mach_msg_type_number_t count;
    if (host_processor_info(mach_host_self(), PROCESSOR_CPU_LOAD_INFO, ncpu, &info, &count) != KERN_SUCCESS) return -1;
    *ticks = malloc(sizeof(unsigned int) * (*ncpu) * CPU_STATE_MAX);
    memcpy(*ticks, info, sizeof(unsigned int) * (*ncpu) * CPU_STATE_MAX);
    vm_deallocate(mach_task_self(), (vm_address_t)info, count * sizeof(int));
    return 0;
}

int main(int argc, char **argv) {
    double interval = 0;
    if (argc >= 3 && strcmp(argv[1], "--watch") == 0) interval = atof(argv[2]);
    int ecores = 0; size_t sz = sizeof(ecores);
    sysctlbyname("hw.perflevel1.physicalcpu", &ecores, &sz, NULL, 0); // perflevel1 = efficiency on Apple silicon
    natural_t n; unsigned int *prev, *cur;
    if (sample(&n, &prev)) return 1;
    for (;;) {
        usleep((useconds_t)((interval > 0 ? interval : 1.0) * 1000000));
        if (sample(&n, &cur)) return 1;
        char line[1024]; size_t pos = 0;
        pos += snprintf(line + pos, sizeof line - pos, "#[bg=default,bold] ");
        // Apple silicon enumerates E-cores first; print P-cores first.
        for (int pass = 0; pass < 2; pass++) {
            int from = pass == 0 ? ecores : 0, to = pass == 0 ? (int)n : ecores;
            for (int i = from; i < to; i++) {
                unsigned int *a = prev + i * CPU_STATE_MAX, *b = cur + i * CPU_STATE_MAX;
                unsigned long busy = (b[CPU_STATE_USER]-a[CPU_STATE_USER]) + (b[CPU_STATE_SYSTEM]-a[CPU_STATE_SYSTEM]) + (b[CPU_STATE_NICE]-a[CPU_STATE_NICE]);
                unsigned long total = busy + (b[CPU_STATE_IDLE]-a[CPU_STATE_IDLE]);
                int level = total ? (int)((busy * 8) / total) : 0; if (level > 7) level = 7;
                pos += snprintf(line + pos, sizeof line - pos, "#[fg=%s]%s", color[level], glyph[level]);
            }
            if (pass == 0 && ecores > 0 && ecores < (int)n) pos += snprintf(line + pos, sizeof line - pos, " ");
        }
        snprintf(line + pos, sizeof line - pos, " #[default]");
        puts(line); fflush(stdout);
        free(prev); prev = cur;
        if (interval <= 0) break;
    }
    return 0;
}
