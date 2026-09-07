/**
 * GENERATED FILE - DO NOT EDIT.
 *
 * Source of truth: AniRec/api/models.py, via FastAPI's OpenAPI document.
 * Regenerate with:  npm run generate:api-types
 * Verify in CI with: npm run verify:api-types
 */
export interface paths {
    "/api/discover/feed": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /**
         * Discover Feed
         * @description The feed, its local votes, and the terms it can be filtered by.
         *
         *     One request rather than three. The three answers are derived from the
         *     same loaded result, and splitting them would let a client render cards
         *     against one generation while filtering them against another.
         */
        get: operations["discover_feed_api_discover_feed_get"];
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/discover/feedback": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        get?: never;
        put?: never;
        /**
         * Discover Feedback
         * @description One vote. Mirrors what the card's three controls write.
         */
        post: operations["discover_feedback_api_discover_feedback_post"];
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/health": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /** Health */
        get: operations["health_api_health_get"];
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/operations": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /** List Operations */
        get: operations["list_operations_api_operations_get"];
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/operations/{kind}": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        get?: never;
        put?: never;
        /** Start Operation */
        post: operations["start_operation_api_operations__kind__post"];
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/operations/{operation_id}": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /** Get Operation */
        get: operations["get_operation_api_operations__operation_id__get"];
        put?: never;
        post?: never;
        /** Cancel Operation */
        delete: operations["cancel_operation_api_operations__operation_id__delete"];
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/operations/{operation_id}/events": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /**
         * Operation Events
         * @description Server-sent events: ``started``, ``progress``/``step``, a terminal
         *     ``result``/``error``/``cancelled``, then ``finished``.
         *
         *     Payload shapes are declared in ``models.ProgressEvent`` and in
         *     ``operations.error_payload``'s corresponding ``ApiError`` field for
         *     ``error``, but are not part of the OpenAPI document FastAPI generates
         *     for this route - it describes the streaming response's envelope, not
         *     the individual frames inside it. ``frontend/src/api/types.ts``
         *     declares these by hand for that reason.
         */
        get: operations["operation_events_api_operations__operation_id__events_get"];
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/system/shutdown": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        get?: never;
        put?: never;
        /**
         * Request Shutdown
         * @description Ask the process to stop serving. The launcher owns the actual exit.
         *
         *     This flips ``uvicorn.Server.should_exit`` when ``__main__.py`` wired
         *     it up as ``on_shutdown_requested`` - the documented way to stop a
         *     server built with ``uvicorn.Server`` from inside a request handler,
         *     which lets in-flight responses (including this one) finish and the
         *     ASGI lifespan close cleanly. Outside a real server (tests, or a
         *     caller that never provided the hook) this is a no-op that still
         *     answers normally, which is deliberate: a test exercising "does this
         *     route exist and require the token" should not need a live server.
         *
         *     The shell holds the child process handle regardless and force-kills
         *     it if this does not result in exit within its own timeout - this
         *     route is the graceful path, not the only path.
         */
        post: operations["request_shutdown_api_system_shutdown_post"];
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/system/state": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /** System State */
        get: operations["system_state_api_system_state_get"];
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/workspace/compare": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /** Compare */
        get: operations["compare_api_workspace_compare_get"];
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/workspace/library": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /** Library */
        get: operations["library_api_workspace_library_get"];
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/workspace/library/resolve": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        get?: never;
        put?: never;
        /** Resolve Title */
        post: operations["resolve_title_api_workspace_library_resolve_post"];
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/workspace/profile": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /** Profile */
        get: operations["profile_api_workspace_profile_get"];
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/workspace/settings": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /** Settings */
        get: operations["settings_api_workspace_settings_get"];
        put?: never;
        /** Save Settings */
        post: operations["save_settings_api_workspace_settings_post"];
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
        /**
         * ApiError
         * @description ``presentable_error``, restated. The desktop error dialog reads the same model.
         */
        ApiError: {
            /** Code */
            code: string;
            /** Description */
            description: string;
            /**
             * Retryable
             * @default false
             */
            retryable: boolean;
            /** Solution */
            solution: string;
            /** Title */
            title: string;
        };
        /**
         * Archetype
         * @description A name for the way this reader differs, and the figures behind it.
         *
         *     The Profile surface used to open with five equal readings and leave the
         *     reader to work out which one was about them. This picks the one that
         *     actually is, so the page can lead with a sentence somebody would repeat
         *     rather than a dashboard nobody asked for.
         */
        Archetype: {
            /** Archetype Id */
            archetype_id: string;
            /**
             * Evidence
             * @default []
             */
            evidence: string[];
            /** Name */
            name: string;
            /** Sentence */
            sentence: string;
        };
        /** Catalogue */
        Catalogue: {
            /** Genres */
            genres: string[];
            /** Statuses */
            statuses: string[];
            /** Studios */
            studios: string[];
            /** Years */
            years: number[];
        };
        /** CompareReadResponse */
        CompareReadResponse: {
            /** Reason */
            reason?: string | null;
            report?: components["schemas"]["CompatibilityReport"] | null;
            /**
             * Sample Names
             * @default []
             */
            sample_names: string[];
        };
        /**
         * ComparisonEntry
         * @description One anime in one comparison section.
         */
        ComparisonEntry: {
            model: components["schemas"]["RecommendationViewModel"];
            scores?: components["schemas"]["ComparisonScores"];
        };
        /**
         * ComparisonScores
         * @description The two opinions on one anime, and the gap between them.
         *
         *     ``difference`` is carried rather than subtracted here on purpose. It is
         *     the backend's figure, so a service that later weights a disagreement by
         *     how confident each rating is can send that instead, and this keeps
         *     working. The frontend only formats it.
         */
        ComparisonScores: {
            /** Difference */
            difference?: number | null;
            /** Friend Score */
            friend_score?: number | null;
            /** Mal Score */
            mal_score?: number | null;
            /** Your Score */
            your_score?: number | null;
        };
        /**
         * ComparisonSection
         * @description A prepared, already-ordered run of anime with a heading.
         *
         *     The frontend does not sort or filter these. Membership and order are the
         *     backend's answer to a question the backend asked; re-ranking them here
         *     would mean the heading no longer describes the contents.
         */
        ComparisonSection: {
            /**
             * Description
             * @default
             */
            description: string;
            /**
             * Empty Message
             * @default
             */
            empty_message: string;
            /**
             * Entries
             * @default []
             */
            entries: components["schemas"]["ComparisonEntry"][];
            /** Section Id */
            section_id: string;
            /** Title */
            title: string;
        };
        /**
         * CompatibilityReport
         * @description Everything one comparison puts on screen.
         */
        CompatibilityReport: {
            friend: components["schemas"]["FriendSummary"];
            /**
             * Is Sample
             * @default false
             */
            is_sample: boolean;
            /**
             * Sections
             * @default []
             */
            sections: components["schemas"]["ComparisonSection"][];
        };
        /** Contribution */
        Contribution: {
            /** Label */
            label: string;
            /** Value */
            value: number;
        };
        /** EraBucket */
        EraBucket: {
            /** Average */
            average?: number | null;
            /** Label */
            label: string;
            /** Watched */
            watched?: number | null;
        };
        /** EraPreferences */
        EraPreferences: {
            /**
             * Buckets
             * @default []
             */
            buckets: components["schemas"]["EraBucket"][];
            golden?: components["schemas"]["EraBucket"] | null;
            /**
             * Season Of Choice
             * @default
             */
            season_of_choice: string;
            /**
             * Seasons
             * @default []
             */
            seasons: components["schemas"]["SeasonReading"][];
        };
        /** ErrorEnvelope */
        ErrorEnvelope: {
            error: components["schemas"]["ApiError"];
        };
        /** FeedResponse */
        FeedResponse: {
            catalogue: components["schemas"]["Catalogue"];
            /** Ephemeral */
            ephemeral: boolean;
            /** Hidden Count */
            hidden_count: number;
            profile: components["schemas"]["ProfileSummary"] | null;
            /** Recommendations */
            recommendations: components["schemas"]["RecommendationViewModelResponse"][];
            /**
             * Source
             * @enum {string}
             */
            source: "profile" | "sample" | "empty";
            state: components["schemas"]["LocalState"];
            /** State Profile Id */
            state_profile_id: string | null;
            /** User Stats */
            user_stats: {
                [key: string]: unknown;
            };
        };
        /** FeedbackRequest */
        FeedbackRequest: {
            /**
             * Action
             * @enum {string}
             */
            action: "hidden" | "watch_later" | "sentiment";
            /**
             * Genres
             * @default []
             */
            genres: string[];
            /** Mal Id */
            mal_id: number;
            /** Profile Id */
            profile_id: string;
            /** Sentiment */
            sentiment?: ("liked" | "disliked") | null;
            /**
             * Title
             * @default
             */
            title: string;
            /**
             * Value
             * @default true
             */
            value: boolean;
        };
        /** FeedbackResponse */
        FeedbackResponse: {
            state: components["schemas"]["LocalState"];
        };
        /**
         * FingerprintReading
         * @description One statistic in the taste fingerprint.
         *
         *     ``readout`` names which instrument draws it - a bank of cells for a
         *     proportion, a two-ended rail for a position between two named extremes -
         *     because the choice belongs with the figure, not with the layout code.
         */
        FingerprintReading: {
            /** Caption */
            caption: string;
            /**
             * Detail
             * @default
             */
            detail: string;
            /**
             * Label
             * @default
             */
            label: string;
            /** Position */
            position?: number | null;
            /** Reading Id */
            reading_id: string;
            /**
             * Readout
             * @default cells
             */
            readout: string;
            /**
             * Scale High
             * @default
             */
            scale_high: string;
            /**
             * Scale Low
             * @default
             */
            scale_low: string;
            /**
             * Tone
             * @default
             */
            tone: string;
            /**
             * Value Text
             * @default N/A
             */
            value_text: string;
        };
        /**
         * FriendSummary
         * @description Who was compared, and the headline figures for the comparison.
         */
        FriendSummary: {
            /** Both Rated */
            both_rated?: number | null;
            /**
             * Match Label
             * @default
             */
            match_label: string;
            /** Match Score */
            match_score?: number | null;
            /** Profile Url */
            profile_url?: string | null;
            /** Shared Anime */
            shared_anime?: number | null;
            /** Total Anime */
            total_anime?: number | null;
            /** Username */
            username: string;
        };
        /** GenreDNA */
        GenreDNA: {
            best_match?: components["schemas"]["GenreVerdict"] | null;
            divisive?: components["schemas"]["GenreVerdict"] | null;
            /**
             * Readings
             * @default []
             */
            readings: components["schemas"]["GenreReading"][];
            weakness?: components["schemas"]["GenreVerdict"] | null;
        };
        /**
         * GenreReading
         * @description One genre: how much of the list it is, and how it was scored.
         */
        GenreReading: {
            /** Average */
            average?: number | null;
            /** Name */
            name: string;
            /** Share */
            share?: number | null;
            /** Spread */
            spread?: number | null;
            /**
             * Titles
             * @default []
             */
            titles: components["schemas"]["TasteTitle"][];
            /** Watched */
            watched?: number | null;
        };
        /**
         * GenreVerdict
         * @description A named genre singled out for one reason, with the figure behind it.
         *
         *     CHANGE [EVIDENCE]: and with the titles behind the figure. "Military is
         *     your most divisive genre" is a claim a reader cannot check and often does
         *     not believe - the usual reaction is "I have watched something tagged
         *     Military?" - so the verdict carries the two ends that made it divisive.
         */
        GenreVerdict: {
            /** Average */
            average?: number | null;
            /**
             * Detail
             * @default
             */
            detail: string;
            /**
             * Lowest
             * @default []
             */
            lowest: components["schemas"]["TasteTitle"][];
            /** Name */
            name: string;
            /** Spread */
            spread?: number | null;
            /**
             * Titles
             * @default []
             */
            titles: components["schemas"]["TasteTitle"][];
            /** Watched */
            watched?: number | null;
        };
        /** HTTPValidationError */
        HTTPValidationError: {
            /** Detail */
            detail?: components["schemas"]["ValidationError"][];
        };
        /**
         * HabitReading
         * @description One behavioural percentage, and where it sits on its own rail.
         */
        HabitReading: {
            /** Caption */
            caption: string;
            /** Position */
            position?: number | null;
            /** Reading Id */
            reading_id: string;
            /**
             * Value Text
             * @default N/A
             */
            value_text: string;
        };
        /** HealthResponse */
        HealthResponse: {
            /**
             * Status
             * @constant
             */
            status: "ok";
            /** Version */
            version: string;
        };
        /**
         * HiddenGems
         * @description Obscure anime this reader rated unusually high.
         */
        HiddenGems: {
            deepest?: components["schemas"]["TitleVerdict"] | null;
            /**
             * Entries
             * @default []
             */
            entries: components["schemas"]["TitleVerdict"][];
            /**
             * Rate Text
             * @default N/A
             */
            rate_text: string;
        };
        /**
         * HotTakes
         * @description The two ends of the same list: rated high, rated low.
         */
        HotTakes: {
            /**
             * Higher
             * @default []
             */
            higher: components["schemas"]["TitleVerdict"][];
            /**
             * Lower
             * @default []
             */
            lower: components["schemas"]["TitleVerdict"][];
        };
        /**
         * HypeKillers
         * @description Highly ranked anime this reader rated unusually low.
         */
        HypeKillers: {
            biggest?: components["schemas"]["TitleVerdict"] | null;
            /** Count */
            count?: number | null;
            /**
             * Entries
             * @default []
             */
            entries: components["schemas"]["TitleVerdict"][];
        };
        /** LibraryReadResponse */
        LibraryReadResponse: {
            /** Profile Id */
            profile_id: string;
            /**
             * Recommendations
             * @default []
             */
            recommendations: components["schemas"]["RecommendationViewModelResponse"][];
        };
        /** LibraryResolveRequest */
        LibraryResolveRequest: {
            /** Mal Id */
            mal_id: number;
            /** Profile Id */
            profile_id: string;
        };
        /** LocalState */
        LocalState: {
            /** Disliked Mal Ids */
            disliked_mal_ids: number[];
            /** Hidden Mal Ids */
            hidden_mal_ids: number[];
            /** Liked Mal Ids */
            liked_mal_ids: number[];
            /** Show Hidden */
            show_hidden: boolean;
            /** Watch Later Mal Ids */
            watch_later_mal_ids: number[];
        };
        /**
         * OperationAcceptedResponse
         * @description What starting an operation returns: a snapshot, at HTTP 202.
         */
        OperationAcceptedResponse: {
            /** Event Count */
            event_count: number;
            /** Id */
            id: string;
            /** Kind */
            kind: string;
            /** Profile Id */
            profile_id: string;
            /**
             * State
             * @enum {string}
             */
            state: "running" | "succeeded" | "failed" | "cancelled";
        };
        /** OperationListResponse */
        OperationListResponse: {
            /** Operations */
            operations: components["schemas"]["OperationSnapshotResponse"][];
        };
        /**
         * OperationSnapshotResponse
         * @description Mirrors ``operations.OperationRecord.snapshot()``.
         *
         *     Named distinctly from ``operations.OperationState`` (the enum the
         *     ``state`` field below draws its literal values from) so the two are never
         *     confused where both are imported.
         */
        OperationSnapshotResponse: {
            /** Event Count */
            event_count: number;
            /** Id */
            id: string;
            /** Kind */
            kind: string;
            /** Profile Id */
            profile_id: string;
            /**
             * State
             * @enum {string}
             */
            state: "running" | "succeeded" | "failed" | "cancelled";
        };
        /**
         * OperationStartRequest
         * @description Every field any operation kind might read; each kind uses a subset.
         *
         *     A single permissive model rather than one per kind, because the kind
         *     itself is a path parameter chosen at request time, not something Pydantic
         *     can discriminate on ahead of it.
         */
        OperationStartRequest: {
            /** Count */
            count?: number | null;
            /** Profile Id */
            profile_id?: string | null;
            /** Target */
            target?: string | null;
            /** Username */
            username?: string | null;
        };
        /**
         * ProfileIdentity
         * @description Who this profile belongs to, and the four counts behind it.
         */
        ProfileIdentity: {
            /** Avatar Url */
            avatar_url?: string | null;
            /** Completed */
            completed?: number | null;
            /** Days Watched */
            days_watched?: number | null;
            /** Episodes */
            episodes?: number | null;
            /** Mean Score */
            mean_score?: number | null;
            /**
             * Member Since
             * @default
             */
            member_since: string;
            /** Profile Url */
            profile_url?: string | null;
            /**
             * Username
             * @default
             */
            username: string;
        };
        /** ProfileReadResponse */
        ProfileReadResponse: {
            archetype?: components["schemas"]["Archetype"] | null;
            profile?: components["schemas"]["TasteProfile"] | null;
            /** Reason */
            reason?: string | null;
        };
        /** ProfileSummary */
        ProfileSummary: {
            /** Profile Id */
            profile_id: string;
            /** Username */
            username: string;
        };
        /** RatingBucket */
        RatingBucket: {
            /**
             * Count
             * @default 0
             */
            count: number;
            /** Score */
            score: number;
        };
        /**
         * RatingDistribution
         * @description The 1-10 histogram, and the four figures read off it.
         *
         *     The buckets arrive from the provider. Mean, median, mode and scale usage
         *     are derived here - see the module docstring for why these four and no
         *     others - and cached, so a resize does not recompute them.
         */
        RatingDistribution: {
            /**
             * Buckets
             * @default []
             */
            buckets: components["schemas"]["RatingBucket"][];
        };
        /**
         * RatingTimeline
         * @description Mean score per year, and the backend's one-word reading of the shape.
         */
        RatingTimeline: {
            /**
             * Points
             * @default []
             */
            points: components["schemas"]["TimelinePoint"][];
            /**
             * Trend
             * @default
             */
            trend: string;
            /**
             * Trend Detail
             * @default
             */
            trend_detail: string;
        };
        /** RecommendationViewModel */
        RecommendationViewModel: {
            /** Alternative Titles */
            alternative_titles: string[];
            /** Contributing Genres */
            contributing_genres: string[];
            /** Cover Url */
            cover_url: string | null;
            /** Display Title */
            display_title: string;
            /** End Date */
            end_date: string;
            /** Episodes */
            episodes: number | null;
            /** Episodes Text */
            episodes_text: string;
            /**
             * Genre Contributions
             * @default []
             */
            genre_contributions: [
                string,
                number
            ][];
            /** Genres */
            genres: string[];
            /** Genres Text */
            genres_text: string;
            /** Large Cover Url */
            large_cover_url: string | null;
            /** Mal Id */
            mal_id: number | null;
            /** Mal Score */
            mal_score: number | null;
            /** Mal Score Text */
            mal_score_text: string;
            /** Mal Url */
            mal_url: string | null;
            /** Media Type */
            media_type?: string | null;
            /** Personal Match */
            personal_match: number;
            /**
             * Personal Match Available
             * @default true
             */
            personal_match_available: boolean;
            /** Personal Match Text */
            personal_match_text: string;
            /** Rank */
            rank: number | null;
            /** Reason */
            reason: string;
            /** Secondary Title */
            secondary_title: string | null;
            /** Start Date */
            start_date: string;
            /** Status */
            status: string;
            /** Studios */
            studios: string[];
            /** Studios Text */
            studios_text: string;
            /** Synopsis */
            synopsis: string;
            /** Year */
            year: number | null;
            /** Year Text */
            year_text: string;
        };
        /**
         * RecommendationViewModelResponse
         * @description ``AniRec.presentation.RecommendationViewModel``, as JSON.
         *
         *     Field-for-field with the dataclass; see ``serialization.view_model_to_dict``.
         *     The ``_text`` fields are pre-formatted for a QLabel and are carried rather
         *     than dropped so this stage changes no behaviour - a browser client should
         *     generally prefer the numeric field beside each one.
         */
        RecommendationViewModelResponse: {
            /** Aired Text */
            aired_text: string | null;
            /** Alternative Titles */
            alternative_titles: string[];
            /** Contributing Genres */
            contributing_genres: string[];
            /** Cover Url */
            cover_url: string | null;
            /** Display Title */
            display_title: string;
            /** End Date */
            end_date: string;
            /** Episodes */
            episodes: number | null;
            /** Episodes Text */
            episodes_text: string;
            /** Genre Contributions */
            genre_contributions: components["schemas"]["Contribution"][];
            /** Genres */
            genres: string[];
            /** Genres Text */
            genres_text: string;
            /** Large Cover Url */
            large_cover_url: string | null;
            /** Mal Id */
            mal_id: number | null;
            /** Mal Score */
            mal_score: number | null;
            /** Mal Score Text */
            mal_score_text: string;
            /** Mal Url */
            mal_url: string | null;
            /** Media Type */
            media_type: string | null;
            /** Personal Match */
            personal_match: number;
            /** Personal Match Available */
            personal_match_available: boolean;
            /** Personal Match Text */
            personal_match_text: string;
            /** Rank */
            rank: number | null;
            /** Reason */
            reason: string;
            /** Secondary Title */
            secondary_title: string | null;
            /** Start Date */
            start_date: string;
            /** Status */
            status: string;
            /** Studios */
            studios: string[];
            /** Studios Text */
            studios_text: string;
            /** Synopsis */
            synopsis: string;
            /** Year */
            year: number | null;
            /** Year Text */
            year_text: string;
        };
        /** RewatchNote */
        RewatchNote: {
            /** Mal Id */
            mal_id?: number | null;
            /** Title */
            title: string;
            /** Watches */
            watches?: number | null;
        };
        /** SeasonReading */
        SeasonReading: {
            /** Average */
            average?: number | null;
            /** Name */
            name: string;
            /** Watched */
            watched?: number | null;
        };
        /** SettingsReadResponse */
        SettingsReadResponse: {
            /** Adventurousness */
            adventurousness: number;
            /** Background Sync */
            background_sync: boolean;
            /** Batch Size */
            batch_size: number;
            /** Client Id Present */
            client_id_present: boolean;
            /**
             * Default Sort
             * @enum {string}
             */
            default_sort: "personal-match" | "mal-score" | "year" | "alphabetical";
            /** Font Scale */
            font_scale: number;
            /** Gui Scale */
            gui_scale: number;
            /** Include Hidden */
            include_hidden: boolean;
            /** Include Nsfw */
            include_nsfw: boolean;
            /** Minimum Mal Score */
            minimum_mal_score: number | null;
            /** Show Covers */
            show_covers: boolean;
            /**
             * Theme
             * @enum {string}
             */
            theme: "system" | "dark" | "light" | "oled" | "gradient";
            /** Username */
            username: string | null;
            /** Using Defaults */
            using_defaults: boolean;
        };
        /** SettingsWriteRequest */
        SettingsWriteRequest: {
            /** Adventurousness */
            adventurousness: number;
            /** Background Sync */
            background_sync: boolean;
            /** Batch Size */
            batch_size: number;
            /**
             * Default Sort
             * @enum {string}
             */
            default_sort: "personal-match" | "mal-score" | "year" | "alphabetical";
            /** Font Scale */
            font_scale: number;
            /** Gui Scale */
            gui_scale: number;
            /** Include Hidden */
            include_hidden: boolean;
            /** Include Nsfw */
            include_nsfw: boolean;
            /** Minimum Mal Score */
            minimum_mal_score: number | null;
            /** Show Covers */
            show_covers: boolean;
            /**
             * Theme
             * @enum {string}
             */
            theme: "system" | "dark" | "light" | "oled" | "gradient";
        };
        /** StudioDNA */
        StudioDNA: {
            most_trusted?: components["schemas"]["StudioReading"] | null;
            most_watched?: components["schemas"]["StudioReading"] | null;
            nemesis?: components["schemas"]["StudioReading"] | null;
            /**
             * Readings
             * @default []
             */
            readings: components["schemas"]["StudioReading"][];
        };
        /**
         * StudioReading
         * @description One studio, and what of theirs this reader actually saw.
         *
         *     A studio name on its own is the weakest fact on the board: most people
         *     cannot name a thing Tezuka Productions made, so "your nemesis studio"
         *     reads as trivia about somebody else. The titles make it about the reader.
         */
        StudioReading: {
            /** Average */
            average?: number | null;
            /**
             * Lowest
             * @default []
             */
            lowest: components["schemas"]["TasteTitle"][];
            /** Name */
            name: string;
            /**
             * Titles
             * @default []
             */
            titles: components["schemas"]["TasteTitle"][];
            /** Watched */
            watched?: number | null;
        };
        /** SystemStateResponse */
        SystemStateResponse: {
            /** Active Operations */
            active_operations: components["schemas"]["OperationSnapshotResponse"][];
            /** Mal Client Id Present */
            mal_client_id_present: boolean;
            /** Needs Setup */
            needs_setup: boolean;
            profile: components["schemas"]["ProfileSummary"] | null;
        };
        /**
         * TasteProfile
         * @description Everything the Profile surface puts on screen, in one answer.
         */
        TasteProfile: {
            eras?: components["schemas"]["EraPreferences"];
            /**
             * Fingerprint
             * @default []
             */
            fingerprint: components["schemas"]["FingerprintReading"][];
            genres?: components["schemas"]["GenreDNA"];
            habits?: components["schemas"]["WatchingHabits"];
            hidden_gems?: components["schemas"]["HiddenGems"];
            hot_takes?: components["schemas"]["HotTakes"];
            hype_killers?: components["schemas"]["HypeKillers"];
            identity?: components["schemas"]["ProfileIdentity"];
            /**
             * Is Sample
             * @default false
             */
            is_sample: boolean;
            rating_distribution?: components["schemas"]["RatingDistribution"];
            studios?: components["schemas"]["StudioDNA"];
            timeline?: components["schemas"]["RatingTimeline"];
        };
        /**
         * TasteTitle
         * @description A title in a genre's drill-down list: a name and one score.
         */
        TasteTitle: {
            /** Title */
            title: string;
            /** Your Score */
            your_score?: number | null;
        };
        /** TimelinePoint */
        TimelinePoint: {
            /** Average */
            average?: number | null;
            /** Rated */
            rated?: number | null;
            /** Year */
            year: number;
        };
        /**
         * TitleVerdict
         * @description One anime and the two opinions on it.
         *
         *     ``delta`` is carried rather than subtracted here for the same reason
         *     ``ComparisonScores.difference`` is: a backend that later weights a
         *     disagreement by how many people rated it can send that instead, and this
         *     keeps working.
         */
        TitleVerdict: {
            /** Community Score */
            community_score?: number | null;
            /** Cover Url */
            cover_url?: string | null;
            /** Delta */
            delta?: number | null;
            /** Mal Id */
            mal_id?: number | null;
            /** Popularity Rank */
            popularity_rank?: number | null;
            /** Ranked Position */
            ranked_position?: number | null;
            /** Title */
            title: string;
            /** Year */
            year?: number | null;
            /** Your Score */
            your_score?: number | null;
        };
        /** ValidationError */
        ValidationError: {
            /** Context */
            ctx?: Record<string, never>;
            /** Input */
            input?: unknown;
            /** Location */
            loc: (string | number)[];
            /** Message */
            msg: string;
            /** Error Type */
            type: string;
        };
        /** WatchingHabits */
        WatchingHabits: {
            most_rewatched?: components["schemas"]["RewatchNote"] | null;
            /**
             * Readings
             * @default []
             */
            readings: components["schemas"]["HabitReading"][];
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
    discover_feed_api_discover_feed_get: {
        parameters: {
            query?: {
                include_hidden?: boolean;
            };
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["FeedResponse"];
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    discover_feedback_api_discover_feedback_post: {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody: {
            content: {
                "application/json": components["schemas"]["FeedbackRequest"];
            };
        };
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["FeedbackResponse"];
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    health_api_health_get: {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HealthResponse"];
                };
            };
            /** @description Unauthorized */
            401: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorEnvelope"];
                };
            };
            /** @description Internal Server Error */
            500: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorEnvelope"];
                };
            };
        };
    };
    list_operations_api_operations_get: {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["OperationListResponse"];
                };
            };
        };
    };
    start_operation_api_operations__kind__post: {
        parameters: {
            query?: never;
            header?: never;
            path: {
                kind: string;
            };
            cookie?: never;
        };
        requestBody?: {
            content: {
                "application/json": components["schemas"]["OperationStartRequest"];
            };
        };
        responses: {
            /** @description Successful Response */
            202: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["OperationAcceptedResponse"];
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    get_operation_api_operations__operation_id__get: {
        parameters: {
            query?: never;
            header?: never;
            path: {
                operation_id: string;
            };
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["OperationSnapshotResponse"];
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    cancel_operation_api_operations__operation_id__delete: {
        parameters: {
            query?: never;
            header?: never;
            path: {
                operation_id: string;
            };
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": {
                        [key: string]: unknown;
                    };
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    operation_events_api_operations__operation_id__events_get: {
        parameters: {
            query?: never;
            header?: never;
            path: {
                operation_id: string;
            };
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": unknown;
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    request_shutdown_api_system_shutdown_post: {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            202: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": {
                        [key: string]: boolean;
                    };
                };
            };
        };
    };
    system_state_api_system_state_get: {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["SystemStateResponse"];
                };
            };
        };
    };
    compare_api_workspace_compare_get: {
        parameters: {
            query?: {
                sample?: boolean;
                username?: string;
            };
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["CompareReadResponse"];
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    library_api_workspace_library_get: {
        parameters: {
            query: {
                profile_id: string;
            };
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["LibraryReadResponse"];
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    resolve_title_api_workspace_library_resolve_post: {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody: {
            content: {
                "application/json": components["schemas"]["LibraryResolveRequest"];
            };
        };
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["RecommendationViewModelResponse"];
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    profile_api_workspace_profile_get: {
        parameters: {
            query?: {
                sample?: boolean;
            };
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ProfileReadResponse"];
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    settings_api_workspace_settings_get: {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["SettingsReadResponse"];
                };
            };
        };
    };
    save_settings_api_workspace_settings_post: {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody: {
            content: {
                "application/json": components["schemas"]["SettingsWriteRequest"];
            };
        };
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["SettingsReadResponse"];
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
}
