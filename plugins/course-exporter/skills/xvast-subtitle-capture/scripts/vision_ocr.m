#import <AppKit/AppKit.h>
#import <Vision/Vision.h>
#import <ImageIO/ImageIO.h>

int main(int argc, const char *argv[]) {
    @autoreleasepool {
        if (argc != 3) {
            fprintf(stderr, "usage: vision_ocr IMAGE_LIST OUTPUT_JSONL\n");
            return 2;
        }
        NSString *listPath = [NSString stringWithUTF8String:argv[1]];
        NSString *outputPath = [NSString stringWithUTF8String:argv[2]];
        NSString *body = [NSString stringWithContentsOfFile:listPath encoding:NSUTF8StringEncoding error:nil];
        if (!body) { fprintf(stderr, "cannot read image list\n"); return 2; }
        if ([[NSFileManager defaultManager] fileExistsAtPath:outputPath]) {
            fprintf(stderr, "refusing to overwrite OCR output\n"); return 2;
        }
        NSArray<NSString *> *paths = [body componentsSeparatedByCharactersInSet:NSCharacterSet.newlineCharacterSet];
        if (![[NSFileManager defaultManager] createFileAtPath:outputPath contents:nil attributes:nil]) {
            fprintf(stderr, "cannot create OCR output\n"); return 2;
        }
        NSFileHandle *handle = [NSFileHandle fileHandleForWritingAtPath:outputPath];
        for (NSString *path in paths) {
            @autoreleasepool {
                if (path.length == 0) continue;
                VNRecognizeTextRequest *request = [VNRecognizeTextRequest new];
                request.recognitionLevel = VNRequestTextRecognitionLevelAccurate;
                request.usesCPUOnly = YES;
                request.recognitionLanguages = @[@"zh-Hans", @"en-US"];
                request.usesLanguageCorrection = YES;
                request.minimumTextHeight = 0.0;
                NSURL *url = [NSURL fileURLWithPath:path];
                NSData *imageData = [NSData dataWithContentsOfURL:url];
                CGImageSourceRef source = imageData ? CGImageSourceCreateWithData((__bridge CFDataRef)imageData, NULL) : NULL;
                CGImageRef cgImage = source ? CGImageSourceCreateImageAtIndex(source, 0, NULL) : NULL;
                NSError *error = nil;
                BOOL ok = NO;
                if (cgImage) {
                    VNImageRequestHandler *runner = [[VNImageRequestHandler alloc] initWithCGImage:cgImage options:@{}];
                    ok = [runner performRequests:@[request] error:&error];
                }
                NSMutableArray *rows = [NSMutableArray array];
                for (VNRecognizedTextObservation *obs in request.results ?: @[]) {
                    VNRecognizedText *top = [[obs topCandidates:1] firstObject];
                    if (!top) continue;
                    CGRect b = obs.boundingBox;
                    [rows addObject:@{@"text": top.string ?: @"", @"confidence": @(top.confidence),
                                      @"x": @(b.origin.x), @"y": @(b.origin.y),
                                      @"w": @(b.size.width), @"h": @(b.size.height)}];
                }
                NSDictionary *result = @{@"image": path, @"rows": rows, @"ok": @(ok),
                                         @"error": error.localizedDescription ?: (cgImage ? @"" : @"Cannot decode input image")};
                NSData *json = [NSJSONSerialization dataWithJSONObject:result options:0 error:nil];
                [handle writeData:json]; [handle writeData:[@"\n" dataUsingEncoding:NSUTF8StringEncoding]];
                if (cgImage) CGImageRelease(cgImage); if (source) CFRelease(source);
            }
        }
        [handle closeFile];
    }
    return 0;
}
