"use client";

// The mic hook lives in lib/recorder.ts (MediaRecorder, live level, elapsed time, snapshot()).
// Re-exported here so screens import every hook from @/hooks.
export { useRecorder, formatTimer, pickRecorderMime, extForMime } from "@/lib/recorder";
export type { Recording, RecorderState } from "@/lib/recorder";
