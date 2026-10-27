// Wake/unlock event bridge. No accessibility APIs, key taps or polling.
#import <AppKit/AppKit.h>

@interface TerminalEvents : NSObject
@property(nonatomic, copy) NSString *directory;
- (void)wake:(NSNotification *)notification;
- (void)unlock:(NSNotification *)notification;
@end
@implementation TerminalEvents
- (void)record:(NSString *)name {
    NSString *value = [NSString stringWithFormat:@"%.0f\n", [[NSDate date] timeIntervalSince1970]];
    NSError *error = nil;
    if (![value writeToFile:[self.directory stringByAppendingPathComponent:name]
                atomically:YES encoding:NSUTF8StringEncoding error:&error])
        NSLog(@"Cannot record terminal event: %@", error);
}
- (void)wake:(NSNotification *)notification { (void)notification; [self record:@"last-wake"]; }
- (void)unlock:(NSNotification *)notification { (void)notification; [self record:@"last-unlock"]; }
@end
int main(int argc, char **argv) {
    @autoreleasepool {
        if (argc != 2) return 2;
        TerminalEvents *events = [TerminalEvents new];
        events.directory = [NSString stringWithUTF8String:argv[1]];
        NSError *error = nil;
        if (![[NSFileManager defaultManager] createDirectoryAtPath:events.directory
                withIntermediateDirectories:YES attributes:nil error:&error]) return 1;
        [[[NSWorkspace sharedWorkspace] notificationCenter] addObserver:events selector:@selector(wake:)
                name:NSWorkspaceDidWakeNotification object:nil];
        [[NSDistributedNotificationCenter defaultCenter] addObserver:events selector:@selector(unlock:)
                name:@"com.apple.screenIsUnlocked" object:nil suspensionBehavior:NSNotificationSuspensionBehaviorDeliverImmediately];
        [[NSRunLoop currentRunLoop] run];
    }
    return 0;
}
