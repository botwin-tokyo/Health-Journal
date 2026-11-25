// Schema digest: 519dcad5d8f964d1885c6314d7f448da96414bfed79b981cde0b0a060c4f6a8d
export interface paths {
    "/api/v1/auth/bootstrap": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /** public_auth_configuration */
        get: operations["GET_api_v1_auth_bootstrap"];
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/v1/session": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /** eligible_account_and_owned_context */
        get: operations["GET_api_v1_session"];
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/v1/session/context": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        get?: never;
        put?: never;
        /** eligible_account_and_owned_context */
        post: operations["POST_api_v1_session_context"];
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/v1/session/activity": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        get?: never;
        put?: never;
        /** eligible_account_and_owned_context */
        post: operations["POST_api_v1_session_activity"];
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/v1/catalog/metrics": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /** current_patient_grant_and_dependencies */
        get: operations["GET_api_v1_catalog_metrics"];
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/v1/overview": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /** current_patient_grant_and_dependencies */
        get: operations["GET_api_v1_overview"];
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/v1/breathing": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /** current_patient_grant_and_dependencies */
        get: operations["GET_api_v1_breathing"];
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/v1/breathing/sessions/{id}": {
        parameters: {
            query?: never;
            header?: never;
            path: {
                id: string;
            };
            cookie?: never;
        };
        /** current_patient_grant_and_dependencies */
        get: operations["GET_api_v1_breathing_sessions_id"];
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/v1/breathing/manual-sessions": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        get?: never;
        put?: never;
        /** owner_only */
        post: operations["POST_api_v1_breathing_manual_sessions"];
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/v1/breathing/sessions/{id}/designation": {
        parameters: {
            query?: never;
            header?: never;
            path: {
                id: string;
            };
            cookie?: never;
        };
        get?: never;
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        /** owner_only */
        patch: operations["PATCH_api_v1_breathing_sessions_id_designation"];
        trace?: never;
    };
    "/api/v1/breathing/imports": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        get?: never;
        put?: never;
        /** owner_only */
        post: operations["POST_api_v1_breathing_imports"];
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/v1/breathing/imports/{id}": {
        parameters: {
            query?: never;
            header?: never;
            path: {
                id: string;
            };
            cookie?: never;
        };
        /** owner_only */
        get: operations["GET_api_v1_breathing_imports_id"];
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/v1/breathing/imports/{id}/review": {
        parameters: {
            query?: never;
            header?: never;
            path: {
                id: string;
            };
            cookie?: never;
        };
        get?: never;
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        /** owner_only */
        patch: operations["PATCH_api_v1_breathing_imports_id_review"];
        trace?: never;
    };
    "/api/v1/breathing/imports/{id}/commit": {
        parameters: {
            query?: never;
            header?: never;
            path: {
                id: string;
            };
            cookie?: never;
        };
        get?: never;
        put?: never;
        /** owner_only */
        post: operations["POST_api_v1_breathing_imports_id_commit"];
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/v1/body": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /** current_patient_grant_and_dependencies */
        get: operations["GET_api_v1_body"];
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/v1/body/weights": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        get?: never;
        put?: never;
        /** owner_only */
        post: operations["POST_api_v1_body_weights"];
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/v1/body/weights/{id}": {
        parameters: {
            query?: never;
            header?: never;
            path: {
                id: string;
            };
            cookie?: never;
        };
        get?: never;
        put?: never;
        post?: never;
        /** owner_only */
        delete: operations["DELETE_api_v1_body_weights_id"];
        options?: never;
        head?: never;
        /** owner_only */
        patch: operations["PATCH_api_v1_body_weights_id"];
        trace?: never;
    };
    "/api/v1/body/days/{date}/representative": {
        parameters: {
            query?: never;
            header?: never;
            path: {
                date: string;
            };
            cookie?: never;
        };
        get?: never;
        /** owner_only */
        put: operations["PUT_api_v1_body_days_date_representative"];
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/v1/sleep-activity": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /** current_patient_grant_and_dependencies */
        get: operations["GET_api_v1_sleep_activity"];
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/v1/activity/workouts/{id}": {
        parameters: {
            query?: never;
            header?: never;
            path: {
                id: string;
            };
            cookie?: never;
        };
        /** current_patient_grant_and_dependencies */
        get: operations["GET_api_v1_activity_workouts_id"];
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/v1/baselines": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /** current_patient_grant_and_dependencies */
        get: operations["GET_api_v1_baselines"];
        put?: never;
        /** owner_only */
        post: operations["POST_api_v1_baselines"];
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/v1/baselines/{id}": {
        parameters: {
            query?: never;
            header?: never;
            path: {
                id: string;
            };
            cookie?: never;
        };
        /** current_patient_grant_and_dependencies */
        get: operations["GET_api_v1_baselines_id"];
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/v1/baselines/preview": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        get?: never;
        put?: never;
        /** owner_only */
        post: operations["POST_api_v1_baselines_preview"];
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/v1/baselines/{id}/retire": {
        parameters: {
            query?: never;
            header?: never;
            path: {
                id: string;
            };
            cookie?: never;
        };
        get?: never;
        put?: never;
        /** owner_only */
        post: operations["POST_api_v1_baselines_id_retire"];
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/v1/journal/entries": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /** current_patient_grant_and_dependencies */
        get: operations["GET_api_v1_journal_entries"];
        put?: never;
        /** owner_only */
        post: operations["POST_api_v1_journal_entries"];
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/v1/journal/entries/{id}": {
        parameters: {
            query?: never;
            header?: never;
            path: {
                id: string;
            };
            cookie?: never;
        };
        /** current_patient_grant_and_dependencies */
        get: operations["GET_api_v1_journal_entries_id"];
        put?: never;
        post?: never;
        /** owner_only */
        delete: operations["DELETE_api_v1_journal_entries_id"];
        options?: never;
        head?: never;
        /** owner_only */
        patch: operations["PATCH_api_v1_journal_entries_id"];
        trace?: never;
    };
    "/api/v1/journal/search": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        get?: never;
        put?: never;
        /** current_patient_grant_and_dependencies */
        post: operations["POST_api_v1_journal_search"];
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/v1/journal/questions": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /** current_patient_grant_and_dependencies */
        get: operations["GET_api_v1_journal_questions"];
        put?: never;
        /** owner_only */
        post: operations["POST_api_v1_journal_questions"];
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/v1/journal/questions/{id}": {
        parameters: {
            query?: never;
            header?: never;
            path: {
                id: string;
            };
            cookie?: never;
        };
        /** current_patient_grant_and_dependencies */
        get: operations["GET_api_v1_journal_questions_id"];
        put?: never;
        post?: never;
        /** owner_only */
        delete: operations["DELETE_api_v1_journal_questions_id"];
        options?: never;
        head?: never;
        /** owner_only */
        patch: operations["PATCH_api_v1_journal_questions_id"];
        trace?: never;
    };
    "/api/v1/journal/medication-events": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /** current_patient_grant_and_dependencies */
        get: operations["GET_api_v1_journal_medication_events"];
        put?: never;
        /** owner_only */
        post: operations["POST_api_v1_journal_medication_events"];
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/v1/journal/medication-events/{id}": {
        parameters: {
            query?: never;
            header?: never;
            path: {
                id: string;
            };
            cookie?: never;
        };
        /** current_patient_grant_and_dependencies */
        get: operations["GET_api_v1_journal_medication_events_id"];
        put?: never;
        post?: never;
        /** owner_only */
        delete: operations["DELETE_api_v1_journal_medication_events_id"];
        options?: never;
        head?: never;
        /** owner_only */
        patch: operations["PATCH_api_v1_journal_medication_events_id"];
        trace?: never;
    };
    "/api/v1/labs/reports": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /** current_patient_grant_and_dependencies */
        get: operations["GET_api_v1_labs_reports"];
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/v1/labs/reports/{id}": {
        parameters: {
            query?: never;
            header?: never;
            path: {
                id: string;
            };
            cookie?: never;
        };
        /** current_patient_grant_and_dependencies */
        get: operations["GET_api_v1_labs_reports_id"];
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/v1/labs/uploads": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        get?: never;
        put?: never;
        /** owner_only */
        post: operations["POST_api_v1_labs_uploads"];
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/v1/labs/imports/{id}": {
        parameters: {
            query?: never;
            header?: never;
            path: {
                id: string;
            };
            cookie?: never;
        };
        /** owner_only */
        get: operations["GET_api_v1_labs_imports_id"];
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/v1/labs/reports/{id}/review": {
        parameters: {
            query?: never;
            header?: never;
            path: {
                id: string;
            };
            cookie?: never;
        };
        get?: never;
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        /** owner_only */
        patch: operations["PATCH_api_v1_labs_reports_id_review"];
        trace?: never;
    };
    "/api/v1/labs/reports/{id}/publish": {
        parameters: {
            query?: never;
            header?: never;
            path: {
                id: string;
            };
            cookie?: never;
        };
        get?: never;
        put?: never;
        /** owner_only */
        post: operations["POST_api_v1_labs_reports_id_publish"];
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/v1/labs/trends": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /** current_patient_grant_and_dependencies */
        get: operations["GET_api_v1_labs_trends"];
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/v1/documents/{id}/content": {
        parameters: {
            query?: never;
            header?: never;
            path: {
                id: string;
            };
            cookie?: never;
        };
        /** exact_document_consent_and_current_grant */
        get: operations["GET_api_v1_documents_id_content"];
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/v1/settings": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /** owner_only */
        get: operations["GET_api_v1_settings"];
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        /** owner_only */
        patch: operations["PATCH_api_v1_settings"];
        trace?: never;
    };
    "/api/v1/devices": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /** owner_only */
        get: operations["GET_api_v1_devices"];
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/v1/devices/{id}/revoke": {
        parameters: {
            query?: never;
            header?: never;
            path: {
                id: string;
            };
            cookie?: never;
        };
        get?: never;
        put?: never;
        /** owner_only */
        post: operations["POST_api_v1_devices_id_revoke"];
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/v1/sync/requests": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        get?: never;
        put?: never;
        /** owner_only */
        post: operations["POST_api_v1_sync_requests"];
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/v1/sync/status": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /** owner_only */
        get: operations["GET_api_v1_sync_status"];
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/v1/sharing/grants": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /** current_patient_grant_and_dependencies */
        get: operations["GET_api_v1_sharing_grants"];
        put?: never;
        /** owner_only */
        post: operations["POST_api_v1_sharing_grants"];
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/v1/sharing/grants/{id}": {
        parameters: {
            query?: never;
            header?: never;
            path: {
                id: string;
            };
            cookie?: never;
        };
        /** current_patient_grant_and_dependencies */
        get: operations["GET_api_v1_sharing_grants_id"];
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        /** owner_only */
        patch: operations["PATCH_api_v1_sharing_grants_id"];
        trace?: never;
    };
    "/api/v1/sharing/grants/{id}/invite": {
        parameters: {
            query?: never;
            header?: never;
            path: {
                id: string;
            };
            cookie?: never;
        };
        get?: never;
        put?: never;
        /** owner_only */
        post: operations["POST_api_v1_sharing_grants_id_invite"];
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/v1/sharing/grants/{id}/revoke": {
        parameters: {
            query?: never;
            header?: never;
            path: {
                id: string;
            };
            cookie?: never;
        };
        get?: never;
        put?: never;
        /** owner_only */
        post: operations["POST_api_v1_sharing_grants_id_revoke"];
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/v1/review/drafts": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /** owner_only */
        get: operations["GET_api_v1_review_drafts"];
        put?: never;
        /** owner_only */
        post: operations["POST_api_v1_review_drafts"];
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/v1/review/drafts/{id}": {
        parameters: {
            query?: never;
            header?: never;
            path: {
                id: string;
            };
            cookie?: never;
        };
        /** owner_only */
        get: operations["GET_api_v1_review_drafts_id"];
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        /** owner_only */
        patch: operations["PATCH_api_v1_review_drafts_id"];
        trace?: never;
    };
    "/api/v1/review/drafts/{id}/snapshots": {
        parameters: {
            query?: never;
            header?: never;
            path: {
                id: string;
            };
            cookie?: never;
        };
        get?: never;
        put?: never;
        /** owner_only */
        post: operations["POST_api_v1_review_drafts_id_snapshots"];
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/v1/review/snapshots/{id}": {
        parameters: {
            query?: never;
            header?: never;
            path: {
                id: string;
            };
            cookie?: never;
        };
        /** artifact_audience_and_every_dependency */
        get: operations["GET_api_v1_review_snapshots_id"];
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/v1/review/snapshots/{id}/exports": {
        parameters: {
            query?: never;
            header?: never;
            path: {
                id: string;
            };
            cookie?: never;
        };
        get?: never;
        put?: never;
        /** owner_only */
        post: operations["POST_api_v1_review_snapshots_id_exports"];
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/v1/exports": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        get?: never;
        put?: never;
        /** owner_only */
        post: operations["POST_api_v1_exports"];
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/v1/exports/{id}": {
        parameters: {
            query?: never;
            header?: never;
            path: {
                id: string;
            };
            cookie?: never;
        };
        /** artifact_audience_and_every_dependency */
        get: operations["GET_api_v1_exports_id"];
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/v1/exports/{id}/download-tickets": {
        parameters: {
            query?: never;
            header?: never;
            path: {
                id: string;
            };
            cookie?: never;
        };
        get?: never;
        put?: never;
        /** current_patient_grant_and_dependencies */
        post: operations["POST_api_v1_exports_id_download_tickets"];
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/v1/exports/{id}/content": {
        parameters: {
            query?: never;
            header?: never;
            path: {
                id: string;
            };
            cookie?: never;
        };
        /** artifact_audience_and_every_dependency */
        get: operations["GET_api_v1_exports_id_content"];
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/v1/security/status": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /** owner_only */
        get: operations["GET_api_v1_security_status"];
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/v1/security/sessions": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /** owner_only */
        get: operations["GET_api_v1_security_sessions"];
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/v1/security/sessions/{id}/revoke": {
        parameters: {
            query?: never;
            header?: never;
            path: {
                id: string;
            };
            cookie?: never;
        };
        get?: never;
        put?: never;
        /** owner_only */
        post: operations["POST_api_v1_security_sessions_id_revoke"];
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/v1/security/access-events": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /** owner_only */
        get: operations["GET_api_v1_security_access_events"];
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/v1/account/deletion-requests": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        get?: never;
        put?: never;
        /** owner_only */
        post: operations["POST_api_v1_account_deletion_requests"];
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/v1/account/deletion-requests/{id}": {
        parameters: {
            query?: never;
            header?: never;
            path: {
                id: string;
            };
            cookie?: never;
        };
        /** owner_only */
        get: operations["GET_api_v1_account_deletion_requests_id"];
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/v1/ingestion/batches": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        get?: never;
        put?: never;
        /** device_namespace_and_scope */
        post: operations["POST_api_v1_ingestion_batches"];
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/v1/ingestion/batches/{batch_id}": {
        parameters: {
            query?: never;
            header?: never;
            path: {
                batch_id: string;
            };
            cookie?: never;
        };
        /** device_namespace_and_scope */
        get: operations["GET_api_v1_ingestion_batches_batch_id"];
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/v1/ingestion/assets": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        get?: never;
        put?: never;
        /** device_namespace_and_scope */
        post: operations["POST_api_v1_ingestion_assets"];
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/v1/ingestion/config": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /** device_namespace_and_scope */
        get: operations["GET_api_v1_ingestion_config"];
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/v1/ingestion/commands/{id}/ack": {
        parameters: {
            query?: never;
            header?: never;
            path: {
                id: string;
            };
            cookie?: never;
        };
        get?: never;
        put?: never;
        /** device_namespace_and_scope */
        post: operations["POST_api_v1_ingestion_commands_id_ack"];
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/v1/blood-pressure": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /** Current blood pressure readings with source qualifications */
        get: operations["GET_api_v1_blood_pressure"];
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
}
export type webhooks = Record<string, never>;
export interface components {
    schemas: {
        Decimal: string;
        Error: {
            error: {
                code: string;
                message: string;
                field_errors: {
                    path?: string;
                    code?: string;
                    message?: string;
                }[];
                request_id?: string | null;
                retryable: boolean;
            };
        };
        Record: {
            /** Format: uuid */
            id: string;
            /** Format: uuid */
            revision_id: string;
            kind: string;
            version: number;
            etag: string;
            clinical_date?: string | null;
            /** Format: date-time */
            received_at?: string;
            data: Record<string, never>;
        };
        Page: {
            items: components["schemas"]["Record"][];
            cursor: string | null;
        };
        WeightInput: {
            value: components["schemas"]["Decimal"];
            /** @enum {unknown} */
            unit: "kg" | "lb";
            /** Format: date */
            clinical_date: string;
            /** @enum {unknown} */
            time_precision: "day" | "minute" | "second";
            measured_start?: string | null;
            measured_end?: string | null;
            timezone?: string;
            original_offset_minutes?: number;
            designation?: {
                /** @enum {unknown} */
                action: "make_representative" | "leave_unchanged";
                expected_etag?: string;
            };
            note_operation?: {
                text: string;
                /** @constant */
                visibility: "private";
            };
        };
        Unavailable: {
            value: null;
            absent_reason: string;
            /** @enum {unknown} */
            availability: "awaiting_data" | "awaiting_integration" | "unavailable" | "partial";
        };
        CommandReceipt: {
            id?: string;
            state?: string;
            status?: string;
            etag?: string;
            context_reset_required?: boolean;
        } & {
            [key: string]: unknown;
        };
        ExportPart: {
            id: string;
            bytes: number;
            mime_type: string;
        } & {
            [key: string]: unknown;
        };
        ExportStatus: {
            id: string;
            /** @enum {unknown} */
            state: "queued" | "running" | "ready" | "failed" | "expired" | "revoked" | "cancelled";
            parts?: components["schemas"]["ExportPart"][];
            error_code?: string;
        } & {
            [key: string]: unknown;
        };
        DownloadTicket: {
            ticket: string;
            part_id: string;
            /** @constant */
            start_deadline_seconds: 60;
        } & {
            [key: string]: unknown;
        };
        LabReview: {
            /** @constant */
            patient_match_confirmed?: true;
            /** @enum {unknown} */
            source_report_status?: "preliminary" | "final" | "corrected" | "unknown";
            clinical_date?: string | null;
            /** @enum {unknown} */
            time_precision?: "day" | "unknown";
            document_only?: boolean;
            results?: components["schemas"]["LabResult"][];
        } & {
            [key: string]: unknown;
        };
        LabResult: {
            label: string;
            raw_result_text: string;
            /** @enum {unknown} */
            value_kind?: "numeric" | "text" | "coded";
            value?: components["schemas"]["Decimal"] | null;
            /** @enum {unknown} */
            operator?: "eq" | "lt" | "le" | "gt" | "ge";
            unit?: string | null;
            excluded?: boolean;
        } & {
            [key: string]: unknown;
        };
        PulmonaryInput: {
            clinical_date: string;
            /** @enum {unknown} */
            time_precision: "day" | "minute" | "second";
            measured_start?: string | null;
            timezone?: string;
            original_offset_minutes?: number;
            /** @enum {unknown} */
            slot?: "morning" | "noon" | "evening" | null;
            values: {
                [key: string]: components["schemas"]["Decimal"] | null;
            };
        } & {
            [key: string]: unknown;
        };
        JournalInput: {
            clinical_date: string;
            time_precision: string;
            title?: string;
            text?: string;
            /** @enum {unknown} */
            visibility?: "private" | "shared";
            tags?: string[];
        } & {
            [key: string]: unknown;
        };
        GrantInput: {
            /** Format: email */
            recipient_email: string;
            from: string;
            to: string;
            categories: ("body" | "breathing" | "sleep_activity" | "labs" | "journal" | "questions")[];
            actions: ("read" | "download_report" | "read_original_document")[];
            record_allowlists: {
                journal: string[];
                questions: string[];
                medication_events: string[];
                labs: string[] | null;
            } & {
                [key: string]: unknown;
            };
            document_ids: string[];
        } & {
            [key: string]: unknown;
        };
        /** @description Authorized page-specific model; missing values remain null with absent_reason. No unrestricted owner payload is returned in a grant context. */
        ReadModel: {
            [key: string]: unknown;
        };
        BatchReceipt: {
            /** Format: uuid */
            batch_id: string;
            state: string;
            /** Format: uri-reference */
            receipt_url: string;
        } & {
            [key: string]: unknown;
        };
        BatchStatus: {
            /** Format: uuid */
            batch_id: string;
            state: string;
            items: ({
                ordinal: number;
                outcome: string;
                reason: string;
                /** Format: uuid */
                record_id: string | null;
                /** Format: uuid */
                revision_id: string | null;
                disposition: string;
            } & {
                [key: string]: unknown;
            })[];
            durably_retained: boolean;
            clinical_acceptance: boolean;
        } & {
            [key: string]: unknown;
        };
        BatchInput: {
            /** @constant */
            schema_version: "pb-health-export-1";
            /** @constant */
            canonicalization: "jcs-rfc8785-v1";
            /** Format: uuid */
            batch_id: string;
            /** Format: uuid */
            source_namespace: string;
            generated_at: string;
            items: unknown[];
        };
    };
    responses: never;
    parameters: never;
    requestBodies: never;
    headers: never;
    pathItems: never;
}
export type $defs = Record<string, never>;
export interface operations {
    GET_api_v1_auth_bootstrap: {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Current authorized response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ReadModel"];
                };
            };
            /** @description Fail-closed structured error; endpoint implementation and release coverage are tracked separately. */
            default: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["Error"];
                };
            };
        };
    };
    GET_api_v1_session: {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Current authorized response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ReadModel"];
                };
            };
            /** @description Fail-closed structured error; endpoint implementation and release coverage are tracked separately. */
            default: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["Error"];
                };
            };
        };
    };
    POST_api_v1_session_context: {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Current authorized response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["CommandReceipt"];
                };
            };
            /** @description Fail-closed structured error; endpoint implementation and release coverage are tracked separately. */
            default: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["Error"];
                };
            };
        };
    };
    POST_api_v1_session_activity: {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Current authorized response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["CommandReceipt"];
                };
            };
            /** @description Fail-closed structured error; endpoint implementation and release coverage are tracked separately. */
            default: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["Error"];
                };
            };
        };
    };
    GET_api_v1_catalog_metrics: {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Current authorized response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ReadModel"];
                };
            };
            /** @description Fail-closed structured error; endpoint implementation and release coverage are tracked separately. */
            default: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["Error"];
                };
            };
        };
    };
    GET_api_v1_overview: {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Current authorized response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ReadModel"];
                };
            };
            /** @description Fail-closed structured error; endpoint implementation and release coverage are tracked separately. */
            default: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["Error"];
                };
            };
        };
    };
    GET_api_v1_breathing: {
        parameters: {
            query?: {
                date?: string;
                from?: string;
                to?: string;
                slot?: "morning" | "noon" | "evening";
            };
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Authorized daily sessions, selected slot, references and dated designated-session history. Inclusive from/to history is bounded to 366 days. */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ReadModel"];
                };
            };
            /** @description Fail-closed structured error; endpoint implementation and release coverage are tracked separately. */
            default: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["Error"];
                };
            };
        };
    };
    GET_api_v1_breathing_sessions_id: {
        parameters: {
            query?: never;
            header?: never;
            path: {
                id: string;
            };
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Current authorized response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["Record"];
                };
            };
            /** @description Fail-closed structured error; endpoint implementation and release coverage are tracked separately. */
            default: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["Error"];
                };
            };
        };
    };
    POST_api_v1_breathing_manual_sessions: {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody: {
            content: {
                "application/json": components["schemas"]["PulmonaryInput"];
            };
        };
        responses: {
            /** @description Current authorized response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["CommandReceipt"];
                };
            };
            /** @description Fail-closed structured error; endpoint implementation and release coverage are tracked separately. */
            default: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["Error"];
                };
            };
        };
    };
    PATCH_api_v1_breathing_sessions_id_designation: {
        parameters: {
            query?: never;
            header?: never;
            path: {
                id: string;
            };
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Current authorized response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["CommandReceipt"];
                };
            };
            /** @description Fail-closed structured error; endpoint implementation and release coverage are tracked separately. */
            default: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["Error"];
                };
            };
        };
    };
    POST_api_v1_breathing_imports: {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Current authorized response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["CommandReceipt"];
                };
            };
            /** @description Fail-closed structured error; endpoint implementation and release coverage are tracked separately. */
            default: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["Error"];
                };
            };
        };
    };
    GET_api_v1_breathing_imports_id: {
        parameters: {
            query?: never;
            header?: never;
            path: {
                id: string;
            };
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Current authorized response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ReadModel"];
                };
            };
            /** @description Fail-closed structured error; endpoint implementation and release coverage are tracked separately. */
            default: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["Error"];
                };
            };
        };
    };
    PATCH_api_v1_breathing_imports_id_review: {
        parameters: {
            query?: never;
            header?: never;
            path: {
                id: string;
            };
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Current authorized response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["CommandReceipt"];
                };
            };
            /** @description Fail-closed structured error; endpoint implementation and release coverage are tracked separately. */
            default: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["Error"];
                };
            };
        };
    };
    POST_api_v1_breathing_imports_id_commit: {
        parameters: {
            query?: never;
            header?: never;
            path: {
                id: string;
            };
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Current authorized response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["CommandReceipt"];
                };
            };
            /** @description Fail-closed structured error; endpoint implementation and release coverage are tracked separately. */
            default: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["Error"];
                };
            };
        };
    };
    GET_api_v1_body: {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Current authorized response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ReadModel"];
                };
            };
            /** @description Fail-closed structured error; endpoint implementation and release coverage are tracked separately. */
            default: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["Error"];
                };
            };
        };
    };
    POST_api_v1_body_weights: {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody: {
            content: {
                "application/json": components["schemas"]["WeightInput"];
            };
        };
        responses: {
            /** @description Current authorized response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["CommandReceipt"];
                };
            };
            /** @description Fail-closed structured error; endpoint implementation and release coverage are tracked separately. */
            default: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["Error"];
                };
            };
        };
    };
    DELETE_api_v1_body_weights_id: {
        parameters: {
            query?: never;
            header?: never;
            path: {
                id: string;
            };
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Current authorized response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["CommandReceipt"];
                };
            };
            /** @description Fail-closed structured error; endpoint implementation and release coverage are tracked separately. */
            default: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["Error"];
                };
            };
        };
    };
    PATCH_api_v1_body_weights_id: {
        parameters: {
            query?: never;
            header?: never;
            path: {
                id: string;
            };
            cookie?: never;
        };
        requestBody: {
            content: {
                "application/json": components["schemas"]["WeightInput"];
            };
        };
        responses: {
            /** @description Current authorized response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["CommandReceipt"];
                };
            };
            /** @description Fail-closed structured error; endpoint implementation and release coverage are tracked separately. */
            default: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["Error"];
                };
            };
        };
    };
    PUT_api_v1_body_days_date_representative: {
        parameters: {
            query?: never;
            header?: never;
            path: {
                date: string;
            };
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Current authorized response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["CommandReceipt"];
                };
            };
            /** @description Fail-closed structured error; endpoint implementation and release coverage are tracked separately. */
            default: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["Error"];
                };
            };
        };
    };
    GET_api_v1_sleep_activity: {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Current authorized response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ReadModel"];
                };
            };
            /** @description Fail-closed structured error; endpoint implementation and release coverage are tracked separately. */
            default: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["Error"];
                };
            };
        };
    };
    GET_api_v1_activity_workouts_id: {
        parameters: {
            query?: never;
            header?: never;
            path: {
                id: string;
            };
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Current authorized response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ReadModel"];
                };
            };
            /** @description Fail-closed structured error; endpoint implementation and release coverage are tracked separately. */
            default: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["Error"];
                };
            };
        };
    };
    GET_api_v1_baselines: {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Current authorized response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ReadModel"];
                };
            };
            /** @description Fail-closed structured error; endpoint implementation and release coverage are tracked separately. */
            default: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["Error"];
                };
            };
        };
    };
    POST_api_v1_baselines: {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Current authorized response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["CommandReceipt"];
                };
            };
            /** @description Fail-closed structured error; endpoint implementation and release coverage are tracked separately. */
            default: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["Error"];
                };
            };
        };
    };
    GET_api_v1_baselines_id: {
        parameters: {
            query?: never;
            header?: never;
            path: {
                id: string;
            };
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Current authorized response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["Record"];
                };
            };
            /** @description Fail-closed structured error; endpoint implementation and release coverage are tracked separately. */
            default: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["Error"];
                };
            };
        };
    };
    POST_api_v1_baselines_preview: {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Current authorized response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["CommandReceipt"];
                };
            };
            /** @description Fail-closed structured error; endpoint implementation and release coverage are tracked separately. */
            default: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["Error"];
                };
            };
        };
    };
    POST_api_v1_baselines_id_retire: {
        parameters: {
            query?: never;
            header?: never;
            path: {
                id: string;
            };
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Current authorized response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["CommandReceipt"];
                };
            };
            /** @description Fail-closed structured error; endpoint implementation and release coverage are tracked separately. */
            default: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["Error"];
                };
            };
        };
    };
    GET_api_v1_journal_entries: {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Current authorized response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ReadModel"];
                };
            };
            /** @description Fail-closed structured error; endpoint implementation and release coverage are tracked separately. */
            default: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["Error"];
                };
            };
        };
    };
    POST_api_v1_journal_entries: {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Current authorized response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["CommandReceipt"];
                };
            };
            /** @description Fail-closed structured error; endpoint implementation and release coverage are tracked separately. */
            default: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["Error"];
                };
            };
        };
    };
    GET_api_v1_journal_entries_id: {
        parameters: {
            query?: never;
            header?: never;
            path: {
                id: string;
            };
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Current authorized response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ReadModel"];
                };
            };
            /** @description Fail-closed structured error; endpoint implementation and release coverage are tracked separately. */
            default: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["Error"];
                };
            };
        };
    };
    DELETE_api_v1_journal_entries_id: {
        parameters: {
            query?: never;
            header?: never;
            path: {
                id: string;
            };
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Current authorized response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["CommandReceipt"];
                };
            };
            /** @description Fail-closed structured error; endpoint implementation and release coverage are tracked separately. */
            default: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["Error"];
                };
            };
        };
    };
    PATCH_api_v1_journal_entries_id: {
        parameters: {
            query?: never;
            header?: never;
            path: {
                id: string;
            };
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Current authorized response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["CommandReceipt"];
                };
            };
            /** @description Fail-closed structured error; endpoint implementation and release coverage are tracked separately. */
            default: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["Error"];
                };
            };
        };
    };
    POST_api_v1_journal_search: {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Current authorized response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["CommandReceipt"];
                };
            };
            /** @description Fail-closed structured error; endpoint implementation and release coverage are tracked separately. */
            default: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["Error"];
                };
            };
        };
    };
    GET_api_v1_journal_questions: {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Current authorized response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ReadModel"];
                };
            };
            /** @description Fail-closed structured error; endpoint implementation and release coverage are tracked separately. */
            default: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["Error"];
                };
            };
        };
    };
    POST_api_v1_journal_questions: {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Current authorized response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["CommandReceipt"];
                };
            };
            /** @description Fail-closed structured error; endpoint implementation and release coverage are tracked separately. */
            default: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["Error"];
                };
            };
        };
    };
    GET_api_v1_journal_questions_id: {
        parameters: {
            query?: never;
            header?: never;
            path: {
                id: string;
            };
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Current authorized response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ReadModel"];
                };
            };
            /** @description Fail-closed structured error; endpoint implementation and release coverage are tracked separately. */
            default: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["Error"];
                };
            };
        };
    };
    DELETE_api_v1_journal_questions_id: {
        parameters: {
            query?: never;
            header?: never;
            path: {
                id: string;
            };
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Current authorized response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["CommandReceipt"];
                };
            };
            /** @description Fail-closed structured error; endpoint implementation and release coverage are tracked separately. */
            default: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["Error"];
                };
            };
        };
    };
    PATCH_api_v1_journal_questions_id: {
        parameters: {
            query?: never;
            header?: never;
            path: {
                id: string;
            };
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Current authorized response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["CommandReceipt"];
                };
            };
            /** @description Fail-closed structured error; endpoint implementation and release coverage are tracked separately. */
            default: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["Error"];
                };
            };
        };
    };
    GET_api_v1_journal_medication_events: {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Current authorized response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ReadModel"];
                };
            };
            /** @description Fail-closed structured error; endpoint implementation and release coverage are tracked separately. */
            default: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["Error"];
                };
            };
        };
    };
    POST_api_v1_journal_medication_events: {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Current authorized response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["CommandReceipt"];
                };
            };
            /** @description Fail-closed structured error; endpoint implementation and release coverage are tracked separately. */
            default: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["Error"];
                };
            };
        };
    };
    GET_api_v1_journal_medication_events_id: {
        parameters: {
            query?: never;
            header?: never;
            path: {
                id: string;
            };
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Current authorized response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ReadModel"];
                };
            };
            /** @description Fail-closed structured error; endpoint implementation and release coverage are tracked separately. */
            default: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["Error"];
                };
            };
        };
    };
    DELETE_api_v1_journal_medication_events_id: {
        parameters: {
            query?: never;
            header?: never;
            path: {
                id: string;
            };
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Current authorized response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["CommandReceipt"];
                };
            };
            /** @description Fail-closed structured error; endpoint implementation and release coverage are tracked separately. */
            default: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["Error"];
                };
            };
        };
    };
    PATCH_api_v1_journal_medication_events_id: {
        parameters: {
            query?: never;
            header?: never;
            path: {
                id: string;
            };
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Current authorized response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["CommandReceipt"];
                };
            };
            /** @description Fail-closed structured error; endpoint implementation and release coverage are tracked separately. */
            default: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["Error"];
                };
            };
        };
    };
    GET_api_v1_labs_reports: {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Current authorized response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ReadModel"];
                };
            };
            /** @description Fail-closed structured error; endpoint implementation and release coverage are tracked separately. */
            default: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["Error"];
                };
            };
        };
    };
    GET_api_v1_labs_reports_id: {
        parameters: {
            query?: never;
            header?: never;
            path: {
                id: string;
            };
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Current authorized response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ReadModel"];
                };
            };
            /** @description Fail-closed structured error; endpoint implementation and release coverage are tracked separately. */
            default: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["Error"];
                };
            };
        };
    };
    POST_api_v1_labs_uploads: {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Current authorized response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["CommandReceipt"];
                };
            };
            /** @description Fail-closed structured error; endpoint implementation and release coverage are tracked separately. */
            default: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["Error"];
                };
            };
        };
    };
    GET_api_v1_labs_imports_id: {
        parameters: {
            query?: never;
            header?: never;
            path: {
                id: string;
            };
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Current authorized response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ReadModel"];
                };
            };
            /** @description Fail-closed structured error; endpoint implementation and release coverage are tracked separately. */
            default: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["Error"];
                };
            };
        };
    };
    PATCH_api_v1_labs_reports_id_review: {
        parameters: {
            query?: never;
            header?: never;
            path: {
                id: string;
            };
            cookie?: never;
        };
        requestBody: {
            content: {
                "application/json": components["schemas"]["LabReview"];
            };
        };
        responses: {
            /** @description Current authorized response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["CommandReceipt"];
                };
            };
            /** @description Fail-closed structured error; endpoint implementation and release coverage are tracked separately. */
            default: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["Error"];
                };
            };
        };
    };
    POST_api_v1_labs_reports_id_publish: {
        parameters: {
            query?: never;
            header?: never;
            path: {
                id: string;
            };
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Current authorized response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["CommandReceipt"];
                };
            };
            /** @description Fail-closed structured error; endpoint implementation and release coverage are tracked separately. */
            default: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["Error"];
                };
            };
        };
    };
    GET_api_v1_labs_trends: {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Current authorized response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ReadModel"];
                };
            };
            /** @description Fail-closed structured error; endpoint implementation and release coverage are tracked separately. */
            default: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["Error"];
                };
            };
        };
    };
    GET_api_v1_documents_id_content: {
        parameters: {
            query?: never;
            header?: never;
            path: {
                id: string;
            };
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Authenticated bounded bytes */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/octet-stream": string;
                };
            };
            /** @description Fail-closed structured error; endpoint implementation and release coverage are tracked separately. */
            default: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["Error"];
                };
            };
        };
    };
    GET_api_v1_settings: {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Current authorized response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ReadModel"];
                };
            };
            /** @description Fail-closed structured error; endpoint implementation and release coverage are tracked separately. */
            default: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["Error"];
                };
            };
        };
    };
    PATCH_api_v1_settings: {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody: {
            content: {
                "application/json": {
                    display_name?: string;
                    /** @enum {string} */
                    time_format?: "12h" | "24h";
                    /** @enum {string} */
                    weight_unit?: "lb" | "kg";
                    timezone?: string;
                    morning_sync?: boolean;
                    pulmonary_windows?: {
                        [key: string]: string[];
                    };
                };
            };
        };
        responses: {
            /** @description Current authorized response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["CommandReceipt"];
                };
            };
            /** @description Fail-closed structured error; endpoint implementation and release coverage are tracked separately. */
            default: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["Error"];
                };
            };
        };
    };
    GET_api_v1_devices: {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Current authorized response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ReadModel"];
                };
            };
            /** @description Fail-closed structured error; endpoint implementation and release coverage are tracked separately. */
            default: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["Error"];
                };
            };
        };
    };
    POST_api_v1_devices_id_revoke: {
        parameters: {
            query?: never;
            header?: never;
            path: {
                id: string;
            };
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Current authorized response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["CommandReceipt"];
                };
            };
            /** @description Fail-closed structured error; endpoint implementation and release coverage are tracked separately. */
            default: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["Error"];
                };
            };
        };
    };
    POST_api_v1_sync_requests: {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Current authorized response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["CommandReceipt"];
                };
            };
            /** @description Fail-closed structured error; endpoint implementation and release coverage are tracked separately. */
            default: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["Error"];
                };
            };
        };
    };
    GET_api_v1_sync_status: {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Current authorized response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ReadModel"];
                };
            };
            /** @description Fail-closed structured error; endpoint implementation and release coverage are tracked separately. */
            default: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["Error"];
                };
            };
        };
    };
    GET_api_v1_sharing_grants: {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Current authorized response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ReadModel"];
                };
            };
            /** @description Fail-closed structured error; endpoint implementation and release coverage are tracked separately. */
            default: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["Error"];
                };
            };
        };
    };
    POST_api_v1_sharing_grants: {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody: {
            content: {
                "application/json": components["schemas"]["GrantInput"];
            };
        };
        responses: {
            /** @description Current authorized response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["CommandReceipt"];
                };
            };
            /** @description Fail-closed structured error; endpoint implementation and release coverage are tracked separately. */
            default: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["Error"];
                };
            };
        };
    };
    GET_api_v1_sharing_grants_id: {
        parameters: {
            query?: never;
            header?: never;
            path: {
                id: string;
            };
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Current authorized response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ReadModel"];
                };
            };
            /** @description Fail-closed structured error; endpoint implementation and release coverage are tracked separately. */
            default: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["Error"];
                };
            };
        };
    };
    PATCH_api_v1_sharing_grants_id: {
        parameters: {
            query?: never;
            header?: never;
            path: {
                id: string;
            };
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Current authorized response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["CommandReceipt"];
                };
            };
            /** @description Fail-closed structured error; endpoint implementation and release coverage are tracked separately. */
            default: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["Error"];
                };
            };
        };
    };
    POST_api_v1_sharing_grants_id_invite: {
        parameters: {
            query?: never;
            header?: never;
            path: {
                id: string;
            };
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Current authorized response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["CommandReceipt"];
                };
            };
            /** @description Fail-closed structured error; endpoint implementation and release coverage are tracked separately. */
            default: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["Error"];
                };
            };
        };
    };
    POST_api_v1_sharing_grants_id_revoke: {
        parameters: {
            query?: never;
            header?: never;
            path: {
                id: string;
            };
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Current authorized response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["CommandReceipt"];
                };
            };
            /** @description Fail-closed structured error; endpoint implementation and release coverage are tracked separately. */
            default: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["Error"];
                };
            };
        };
    };
    GET_api_v1_review_drafts: {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Current authorized response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ReadModel"];
                };
            };
            /** @description Fail-closed structured error; endpoint implementation and release coverage are tracked separately. */
            default: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["Error"];
                };
            };
        };
    };
    POST_api_v1_review_drafts: {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Current authorized response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["CommandReceipt"];
                };
            };
            /** @description Fail-closed structured error; endpoint implementation and release coverage are tracked separately. */
            default: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["Error"];
                };
            };
        };
    };
    GET_api_v1_review_drafts_id: {
        parameters: {
            query?: never;
            header?: never;
            path: {
                id: string;
            };
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Current authorized response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ReadModel"];
                };
            };
            /** @description Fail-closed structured error; endpoint implementation and release coverage are tracked separately. */
            default: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["Error"];
                };
            };
        };
    };
    PATCH_api_v1_review_drafts_id: {
        parameters: {
            query?: never;
            header?: never;
            path: {
                id: string;
            };
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Current authorized response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["CommandReceipt"];
                };
            };
            /** @description Fail-closed structured error; endpoint implementation and release coverage are tracked separately. */
            default: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["Error"];
                };
            };
        };
    };
    POST_api_v1_review_drafts_id_snapshots: {
        parameters: {
            query?: never;
            header?: never;
            path: {
                id: string;
            };
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Current authorized response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["CommandReceipt"];
                };
            };
            /** @description Fail-closed structured error; endpoint implementation and release coverage are tracked separately. */
            default: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["Error"];
                };
            };
        };
    };
    GET_api_v1_review_snapshots_id: {
        parameters: {
            query?: never;
            header?: never;
            path: {
                id: string;
            };
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Current authorized response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["Record"];
                };
            };
            /** @description Fail-closed structured error; endpoint implementation and release coverage are tracked separately. */
            default: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["Error"];
                };
            };
        };
    };
    POST_api_v1_review_snapshots_id_exports: {
        parameters: {
            query?: never;
            header?: never;
            path: {
                id: string;
            };
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Current authorized response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["CommandReceipt"];
                };
            };
            /** @description Fail-closed structured error; endpoint implementation and release coverage are tracked separately. */
            default: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["Error"];
                };
            };
        };
    };
    POST_api_v1_exports: {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Current authorized response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["CommandReceipt"];
                };
            };
            /** @description Fail-closed structured error; endpoint implementation and release coverage are tracked separately. */
            default: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["Error"];
                };
            };
        };
    };
    GET_api_v1_exports_id: {
        parameters: {
            query?: never;
            header?: never;
            path: {
                id: string;
            };
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Current authorized response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ExportStatus"];
                };
            };
            /** @description Fail-closed structured error; endpoint implementation and release coverage are tracked separately. */
            default: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["Error"];
                };
            };
        };
    };
    POST_api_v1_exports_id_download_tickets: {
        parameters: {
            query?: never;
            header?: never;
            path: {
                id: string;
            };
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Current authorized response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["DownloadTicket"];
                };
            };
            /** @description Fail-closed structured error; endpoint implementation and release coverage are tracked separately. */
            default: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["Error"];
                };
            };
        };
    };
    GET_api_v1_exports_id_content: {
        parameters: {
            query?: never;
            header?: never;
            path: {
                id: string;
            };
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Authenticated bounded bytes */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/octet-stream": string;
                };
            };
            /** @description Fail-closed structured error; endpoint implementation and release coverage are tracked separately. */
            default: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["Error"];
                };
            };
        };
    };
    GET_api_v1_security_status: {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Current authorized response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ReadModel"];
                };
            };
            /** @description Fail-closed structured error; endpoint implementation and release coverage are tracked separately. */
            default: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["Error"];
                };
            };
        };
    };
    GET_api_v1_security_sessions: {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Current authorized response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ReadModel"];
                };
            };
            /** @description Fail-closed structured error; endpoint implementation and release coverage are tracked separately. */
            default: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["Error"];
                };
            };
        };
    };
    POST_api_v1_security_sessions_id_revoke: {
        parameters: {
            query?: never;
            header?: never;
            path: {
                id: string;
            };
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Current authorized response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["CommandReceipt"];
                };
            };
            /** @description Fail-closed structured error; endpoint implementation and release coverage are tracked separately. */
            default: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["Error"];
                };
            };
        };
    };
    GET_api_v1_security_access_events: {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Current authorized response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ReadModel"];
                };
            };
            /** @description Fail-closed structured error; endpoint implementation and release coverage are tracked separately. */
            default: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["Error"];
                };
            };
        };
    };
    POST_api_v1_account_deletion_requests: {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Current authorized response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["CommandReceipt"];
                };
            };
            /** @description Fail-closed structured error; endpoint implementation and release coverage are tracked separately. */
            default: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["Error"];
                };
            };
        };
    };
    GET_api_v1_account_deletion_requests_id: {
        parameters: {
            query?: never;
            header?: never;
            path: {
                id: string;
            };
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Current authorized response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ReadModel"];
                };
            };
            /** @description Fail-closed structured error; endpoint implementation and release coverage are tracked separately. */
            default: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["Error"];
                };
            };
        };
    };
    POST_api_v1_ingestion_batches: {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody: {
            content: {
                "application/json": components["schemas"]["BatchInput"];
            };
        };
        responses: {
            /** @description Identical batch replay; current state and original receipt URL */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["BatchReceipt"];
                };
            };
            /** @description New batch durably received and queued for item processing */
            202: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["BatchReceipt"];
                };
            };
            /** @description Batch ID already used with different content or by another device */
            409: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["Error"];
                };
            };
            /** @description Fail-closed structured error; endpoint implementation and release coverage are tracked separately. */
            default: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["Error"];
                };
            };
        };
    };
    GET_api_v1_ingestion_batches_batch_id: {
        parameters: {
            query?: never;
            header?: never;
            path: {
                batch_id: string;
            };
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Device-scoped status and current per-item outcomes */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["BatchStatus"];
                };
            };
            /** @description Fail-closed structured error; endpoint implementation and release coverage are tracked separately. */
            default: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["Error"];
                };
            };
        };
    };
    POST_api_v1_ingestion_assets: {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Current authorized response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["CommandReceipt"];
                };
            };
            /** @description Fail-closed structured error; endpoint implementation and release coverage are tracked separately. */
            default: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["Error"];
                };
            };
        };
    };
    GET_api_v1_ingestion_config: {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Current authorized response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ReadModel"];
                };
            };
            /** @description Fail-closed structured error; endpoint implementation and release coverage are tracked separately. */
            default: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["Error"];
                };
            };
        };
    };
    POST_api_v1_ingestion_commands_id_ack: {
        parameters: {
            query?: never;
            header?: never;
            path: {
                id: string;
            };
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Current authorized response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["CommandReceipt"];
                };
            };
            /** @description Fail-closed structured error; endpoint implementation and release coverage are tracked separately. */
            default: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["Error"];
                };
            };
        };
    };
    GET_api_v1_blood_pressure: {
        parameters: {
            query?: {
                from?: string;
                to?: string;
                cursor?: string;
            };
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Current authorized response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ReadModel"];
                };
            };
            /** @description Fail-closed structured error; endpoint implementation and release coverage are tracked separately. */
            default: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["Error"];
                };
            };
        };
    };
}
