// Battery segment for the Byobu status bar: charge gauge, percentage, AC bolt and time
// remaining. The draw is averaged over a rolling window and used only to
// derive the estimate, never displayed.
// Reads AppleSmartBattery through IOKit (no forks, no powermetrics/root).
// Shown signed: negative while discharging, positive while charging, followed
// by the time left, derived from the remaining charge and the averaged draw
// (steadier than the firmware's own TimeRemaining estimate).
// Usage: tmux-watts [--watch SECONDS] [--window SECONDS]
#include <CoreFoundation/CoreFoundation.h>
#include <IOKit/IOKitLib.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <unistd.h>

static int number(CFDictionaryRef d, CFStringRef key, long long *out) {
    CFNumberRef n = CFDictionaryGetValue(d, key);
    if (!n || CFGetTypeID(n) != CFNumberGetTypeID()) return 0;
    return CFNumberGetValue(n, kCFNumberLongLongType, out);
}

int main(int argc, char **argv) {
    double interval = 2.0, window = 30.0;
    for (int i = 1; i + 1 < argc; i += 2) {
        if (!strcmp(argv[i], "--watch")) interval = atof(argv[i + 1]);
        else if (!strcmp(argv[i], "--window")) window = atof(argv[i + 1]);
    }
    if (interval <= 0) interval = 2.0;
    int slots = (int)(window / interval + 0.5); if (slots < 1) slots = 1;
    double *ring = calloc(slots, sizeof(double));
    int filled = 0, next = 0;

    for (;;) {
        io_service_t svc = IOServiceGetMatchingService(kIOMainPortDefault, IOServiceMatching("AppleSmartBattery"));
        double watts = -1, reserve = -1; int charging = 0, plugged_in = 0; long long pct = -1;
        if (svc) {
            CFMutableDictionaryRef props = NULL;
            if (IORegistryEntryCreateCFProperties(svc, &props, kCFAllocatorDefault, 0) == KERN_SUCCESS && props) {
                long long amp = 0, volt = 0, cur = 0, max = 0;
                plugged_in = CFDictionaryGetValue(props, CFSTR("ExternalConnected")) == kCFBooleanTrue;
                if (number(props, CFSTR("InstantAmperage"), &amp) && number(props, CFSTR("Voltage"), &volt)) {
                    charging = amp > 0;
                    watts = (amp < 0 ? -amp : amp) / 1000.0 * (volt / 1000.0);
                    // Energy still to give (discharging) or still to take (charging).
                    number(props, CFSTR("CurrentCapacity"), &pct);
                    if (number(props, CFSTR("AppleRawCurrentCapacity"), &cur) &&
                        number(props, CFSTR("AppleRawMaxCapacity"), &max))
                        reserve = (charging ? (double)(max - cur) : (double)cur) / 1000.0 * (volt / 1000.0);
                }
                CFRelease(props);
            }
            IOObjectRelease(svc);
        }
        if (watts >= 0) { ring[next] = watts; next = (next + 1) % slots; if (filled < slots) filled++; }
        if (filled) {
            double sum = 0; for (int i = 0; i < filled; i++) sum += ring[i];
            double avg = sum / filled;
            const char *gauge = pct >= 88 ? "\u25b0\u25b0\u25b0\u25b0" : pct >= 63 ? "\u25b0\u25b0\u25b0\u25b1"
                             : pct >= 38 ? "\u25b0\u25b0\u25b1\u25b1" : pct >= 13 ? "\u25b0\u25b1\u25b1\u25b1"
                             : "\u25b1\u25b1\u25b1\u25b1";
            printf("#[fg=#111827,bg=#fde047,bold] ");
            if (pct >= 0) printf("%s %lld%%", gauge, pct);
            if (plugged_in) printf(" \u03df");
            if (reserve > 0 && avg > 0.2) {
                int mins = (int)(reserve / avg * 60 + 0.5);
                printf(" %s%dh%02dm", charging ? "+" : "", mins / 60, mins % 60);
            }
            printf(" ");
        }
        printf("#[default]\n");
        fflush(stdout);
        usleep((useconds_t)(interval * 1000000));
    }
    return 0;
}
