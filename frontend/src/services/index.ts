export { default as ApiService } from './api.service';
export { default as AuthService } from './auth.service';
export { default as LocationService } from './location.service';
export { default as NotificationService } from './notification.service';
export { crimeService } from './crime.service';
export type { CrimeAnalysisResult } from './crime.service';
// `speechService` was removed in B8 along with `hooks/useVoiceRecorder`.
// Both existed only to record a clip and upload it to /ai/speech-to-text so the
// hot-words screen could fill in a text field. Hot-word dictation is now
// on-device (`features/voice/dictate.ts`), which left them with no callers --
// and an unused path that uploads a recording of someone's voice is not the
// kind of dead code to leave lying about. The backend's /ai/speech-to-text is
// untouched (defect 2 still applies to it; that is B4).
export { riskService } from './risk.service';
export type { RiskFlagsResult, MapRegion } from './risk.service';
