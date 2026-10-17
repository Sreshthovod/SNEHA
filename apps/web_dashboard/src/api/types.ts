/**
 * Domain types for the SNEHA API, derived from the GENERATED schema.d.ts
 * (source: packages/api_contracts/openapi.json). Never hand-edit shapes here.
 */
import type { components } from './schema'

type S<K extends keyof components['schemas']> = components['schemas'][K]

export type UserRole = S<'UserRole'>
export type User = S<'UserOut'>
export type TokenResponse = S<'TokenResponse'>
export type LoginRequest = S<'LoginRequest'>
export type RegisterRequest = S<'RegisterRequest'>

export type Language = S<'Language'>
export type Patient = S<'PatientOut'>
export type PatientCreate = S<'PatientCreate'>
export type PatientUpdate = S<'PatientUpdate'>
export type PairingCode = S<'PairingCodeOut'>
export type Caregiver = S<'CaregiverOut'>
export type CaregiverAdd = S<'CaregiverAdd'>
export type ClinicianGrant = S<'ClinicianGrantOut'>
export type ClinicianGrantCreate = S<'ClinicianGrantCreate'>

export type ConsentType = S<'ConsentType'>
export type ConsentStatus = S<'ConsentStatus'>
export type ConsentGiver = S<'ConsentGiver'>
export type Consent = S<'ConsentOut'>
export type ConsentCreate = S<'ConsentCreate'>
export type ConsentSummary = S<'ConsentSummary'>

export type MemoryKind = S<'MemoryKind'>
export type MemoryStatus = S<'MemoryStatus'>
export type Memory = S<'MemoryOut'>
export type MemoryLink = S<'MemoryRelationshipOut'>
export type MemoryLinkCreate = S<'MemoryRelationshipCreate'>
export type MemoryLinkType = S<'MemoryRelationType'>
export type MemoryCreate = S<'MemoryCreate'>
export type MemoryCorrection = S<'MemoryCorrection'>
export type MemoryReview = S<'MemoryReview'>
export type StoredFile = S<'FileOut'>

export type ObservationCategory = S<'ObservationCategory'>
export type ObservationStatus = S<'ObservationStatus'>
export type RecordSource = S<'RecordSource'>
export type Observation = S<'ObservationOut'>
export type ObservationCreate = S<'ObservationCreate'>
export type ObservationCorrection = S<'ObservationCorrection'>
export type ObservationReview = S<'ObservationReview'>
export type ObservationResolve = S<'ObservationResolve'>
export type ObservationRevision = S<'ObservationRevisionOut'>
export type FatigueLevel = S<'FatigueLevel'>

export type ReviewItem = S<'ReviewItemOut'>
export type ReviewItemStatus = S<'ReviewItemStatus'>
export type ReviewDecision = S<'ReviewDecision'>
export type SessionEvent = S<'EventOut'>
export type ActivityEventType = S<'ActivityEventType'>

export type AnalyticsSummary = S<'AnalyticsSummary'>
export type AnalyticsTotals = S<'Totals'>
export type ActivityMetrics = S<'ActivityMetrics'>
export type ActivityPreference = S<'ActivityPreference'>
export type BaselineSummary = S<'BaselineSummary'>
export type BaselineComparison = S<'BaselineComparison'>
export type Completeness = S<'Completeness'>
export type DailyMetrics = S<'DailyMetrics'>
export type EngagementCounts = S<'EngagementCounts'>
export type ContextObservation = S<'ContextObservation'>
export type ReviewFlag = S<'ReviewFlag'>
export type ReviewFlagsResponse = S<'ReviewFlagsResponse'>
export type RuleNotEvaluated = S<'RuleNotEvaluated'>

export type CatalogEntry = S<'CatalogEntry'>
export type Preferences = S<'PreferencesOut'>
export type PreferencesUpdate = S<'PreferencesUpdate'>
export type Progress = S<'ProgressOut'>
export type ActivityProgress = S<'ActivityProgress'>
export type Recommendation = S<'RecommendationOut'>
export type RecommendationAction = S<'RecommendationAction'>
export type Supporting = S<'SupportOut'>
export type ResultSubmissionOut = S<'ResultSubmissionOut'>

export type Activity = S<'ActivityDefinitionOut'>
export type Session = S<'SessionOut'>
export type Result = S<'ResultOut'>
export type PerformanceHistory = S<'PerformanceHistory'>
export type HistoryDay = S<'HistoryDay'>

export type ReportStatus = S<'ReportStatus'>
export type Report = S<'ReportOut'>
export type ReportRequest = S<'ReportRequest'>

export type HealthResponse = S<'HealthResponse'>
export type ReadinessResponse = S<'ReadinessResponse'>
export type ReadinessCheck = S<'ReadinessCheck'>
export type ConfigStatus = S<'ConfigStatus'>
export type ErrorBody = S<'ErrorBody'>
export type ErrorResponse = S<'ErrorResponse'>
