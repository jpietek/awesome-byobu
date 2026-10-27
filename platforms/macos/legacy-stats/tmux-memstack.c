// RAM as a stacked bar for the Byobu status bar. One host_statistics64 call
// and one sysctl per tick, no forks. Cells: wired (red), app (green),
// compressed (purple), cached (dim), free (empty). The percentage is
// Activity Monitor's "memory used" (app + wired + compressed). The block's
// background follows the kernel memory-pressure level.
// Usage: tmux-memstack [--watch SECONDS]
#include <mach/mach.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <unistd.h>
#include <sys/sysctl.h>

#define CELLS 8

int main(int argc, char **argv) {
    double interval = 0;
    if (argc >= 3 && strcmp(argv[1], "--watch") == 0) interval = atof(argv[2]);
    uint64_t total = 0; size_t sz = sizeof total;
    sysctlbyname("hw.memsize", &total, &sz, NULL, 0);
    vm_size_t page = 0; host_page_size(mach_host_self(), &page);
    for (;;) {
        vm_statistics64_data_t vm; mach_msg_type_number_t cnt = HOST_VM_INFO64_COUNT;
        if (host_statistics64(mach_host_self(), HOST_VM_INFO64, (host_info64_t)&vm, &cnt) != KERN_SUCCESS) return 1;
        double wired = (double)vm.wire_count * page;
        double app = ((double)vm.internal_page_count - (double)vm.purgeable_count) * page; if (app < 0) app = 0;
        double comp = (double)vm.compressor_page_count * page;
        double cached = ((double)vm.external_page_count + (double)vm.purgeable_count) * page;
        double used = wired + app + comp;
        // Smooth with an exponential moving average so the bar drifts instead
        // of flipping whole cells on small fluctuations.
        static double sm[4] = {-1, -1, -1, -1}; double raw[4] = {wired, app, comp, cached};
        for (int i = 0; i < 4; i++) sm[i] = sm[i] < 0 ? raw[i] : sm[i] * 0.7 + raw[i] * 0.3;
        const char *col[4] = {"#f87171", "#4ade80", "#c084fc", "#64748b"};
        // Cumulative boundaries in half-cells (resolution: total / (2*CELLS)).
        int half[5] = {0}; double acc = 0;
        for (int i = 0; i < 4; i++) { acc += sm[i]; half[i+1] = (int)(acc / total * CELLS * 2 + 0.5); if (half[i+1] > CELLS*2) half[i+1] = CELLS*2; }
        int level = 1; sz = sizeof level;
        sysctlbyname("kern.memorystatus_vm_pressure_level", &level, &sz, NULL, 0);
        const char *bg = level >= 4 ? "#dc2626" : level >= 2 ? "#facc15" : "#1e293b";
        const char *fg = level >= 2 ? "#111827" : "#e2e8f0";
        printf("#[fg=%s,bg=%s,bold] ", fg, bg);
        // Render cell by cell: a cell whose two halves belong to different
        // types is drawn as a left-half block in the first type's colour on
        // the second type's colour background.
        for (int c = 0; c < CELLS; c++) {
            int h0 = c * 2, h1 = c * 2 + 1, t0 = 4, t1 = 4;
            for (int i = 0; i < 4; i++) { if (h0 >= half[i] && h0 < half[i+1]) t0 = i; if (h1 >= half[i] && h1 < half[i+1]) t1 = i; }
            const char *c0 = t0 < 4 ? col[t0] : "#334155", *c1 = t1 < 4 ? col[t1] : "#334155";
            if (t0 == t1) printf("#[fg=%s,bg=%s]%s", c0, bg, t0 < 4 ? "\u2588" : "\u2591");
            else printf("#[fg=%s,bg=%s]\u258c#[bg=%s]", c0, t1 < 4 ? c1 : bg, bg);
        }
        printf("#[fg=%s] %.0f%% #[default]\n", fg, used / total * 100);
        fflush(stdout);
        if (interval <= 0) break;
        usleep((useconds_t)(interval * 1000000));
    }
    return 0;
}
