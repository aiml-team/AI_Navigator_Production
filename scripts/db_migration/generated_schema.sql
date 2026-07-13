/* ====================================================================
   Auto-generated DDL from source DB: AI-Navigator
   Target: AI-Navigator-Prod (created empty; safe to apply once).
   Do not edit by hand; regenerate with scripts/db_migration/02_extract_ddl.py.
   ==================================================================== */



-- ── Tables ─────────────────────────────────────────────
CREATE TABLE [dbo].[admin_users] (
    [id] NVARCHAR(36) NOT NULL,
    [email] NVARCHAR(255) NOT NULL,
    [password_hash] NVARCHAR(255) NOT NULL,
    [full_name] NVARCHAR(255) NULL DEFAULT (''),
    [role] NVARCHAR(50) NULL DEFAULT ('admin'),
    [is_active] INT NULL DEFAULT ((1)),
    [created_at] NVARCHAR(50) NULL,
    [last_login] NVARCHAR(50) NULL,
    CONSTRAINT [PK__admin_us__3213E83FDA8DF879] PRIMARY KEY CLUSTERED ([id] ASC),
    CONSTRAINT [UQ__admin_us__AB6E616431103204] UNIQUE NONCLUSTERED ([email] ASC)
);

CREATE TABLE [dbo].[audit_log] (
    [id] NVARCHAR(36) NOT NULL,
    [created_at] NVARCHAR(50) NULL,
    [raw_input] NVARCHAR(MAX) NULL,
    [intent] NVARCHAR(255) NULL,
    [industry] NVARCHAR(255) NULL,
    [recommended_tool] NVARCHAR(255) NULL,
    [tool_reason] NVARCHAR(MAX) NULL,
    [tool_confidence] NVARCHAR(50) NULL,
    [policy_flags] NVARCHAR(MAX) NULL,
    [retrieved_policies] NVARCHAR(MAX) NULL,
    [final_prompt] NVARCHAR(MAX) NULL,
    [prompt_version] NVARCHAR(50) NULL,
    [model_used] NVARCHAR(255) NULL,
    [output] NVARCHAR(MAX) NULL,
    [token_estimate] INT NULL DEFAULT ((0)),
    [system_version] NVARCHAR(50) NULL,
    [policy_blocked] INT NULL DEFAULT ((0)),
    [policy_summary] NVARCHAR(MAX) NULL DEFAULT (''),
    [role] NVARCHAR(255) NULL DEFAULT ('general'),
    [user_email] NVARCHAR(255) NULL DEFAULT (''),
    [row_num] INT IDENTITY(1,1) NOT NULL,
    [task_source] NVARCHAR(50) NULL DEFAULT ('typed'),
    [scenario_id] NVARCHAR(64) NULL DEFAULT (''),
    [scenario_title] NVARCHAR(500) NULL DEFAULT (''),
    CONSTRAINT [PK__audit_lo__3213E83FE92D7010] PRIMARY KEY CLUSTERED ([id] ASC),
    CONSTRAINT [UQ_audit_log_row_num] UNIQUE NONCLUSTERED ([row_num] ASC)
);

CREATE TABLE [dbo].[feedback] (
    [id] NVARCHAR(36) NOT NULL,
    [audit_id] NVARCHAR(36) NULL,
    [email] NVARCHAR(255) NULL DEFAULT (''),
    [rating] INT NULL,
    [comment] NVARCHAR(MAX) NULL,
    [issue_type] NVARCHAR(255) NULL,
    [created_at] NVARCHAR(50) NULL,
    [source] NVARCHAR(50) NULL DEFAULT ('form'),
    [files] NVARCHAR(MAX) NULL DEFAULT ('[]'),
    [task_source] NVARCHAR(50) NULL DEFAULT (''),
    CONSTRAINT [PK__feedback__3213E83F0A363E78] PRIMARY KEY CLUSTERED ([id] ASC)
);

CREATE TABLE [dbo].[NavigatorAdmins] (
    [id] INT IDENTITY(1,1) NOT NULL,
    [email] NVARCHAR(255) NOT NULL,
    [name] NVARCHAR(255) NULL DEFAULT (''),
    [added_at] DATETIME2 NULL DEFAULT (getutcdate()),
    CONSTRAINT [PK__Navigato__3213E83FD5A58D7B] PRIMARY KEY CLUSTERED ([id] ASC),
    CONSTRAINT [UQ__Navigato__AB6E616466A8E038] UNIQUE NONCLUSTERED ([email] ASC)
);

CREATE TABLE [dbo].[NavigatorUsers] (
    [id] INT IDENTITY(1,1) NOT NULL,
    [email] NVARCHAR(255) NOT NULL,
    [name] NVARCHAR(255) NULL DEFAULT (''),
    [first_seen] DATETIME2 NULL DEFAULT (getutcdate()),
    [last_seen] DATETIME2 NULL DEFAULT (getutcdate()),
    CONSTRAINT [PK__Navigato__3213E83FC6AC296B] PRIMARY KEY CLUSTERED ([id] ASC),
    CONSTRAINT [UQ__Navigato__AB6E6164A57A3C9A] UNIQUE NONCLUSTERED ([email] ASC)
);

CREATE TABLE [dbo].[prompt_versions] (
    [id] NVARCHAR(36) NOT NULL,
    [version] NVARCHAR(50) NOT NULL,
    [intent] NVARCHAR(255) NULL,
    [industry] NVARCHAR(255) NULL,
    [template] NVARCHAR(MAX) NOT NULL,
    [change_note] NVARCHAR(MAX) NULL,
    [created_at] NVARCHAR(50) NULL,
    [created_by] NVARCHAR(255) NULL DEFAULT ('system'),
    CONSTRAINT [PK__prompt_v__3213E83F742DA5FA] PRIMARY KEY CLUSTERED ([id] ASC)
);

CREATE TABLE [dbo].[registered_tools] (
    [id] NVARCHAR(36) NOT NULL,
    [tool_name] NVARCHAR(255) NOT NULL,
    [description] NVARCHAR(MAX) NULL DEFAULT (''),
    [category] NVARCHAR(255) NULL DEFAULT (''),
    [url] NVARCHAR(500) NULL DEFAULT (''),
    [icon] NVARCHAR(255) NULL DEFAULT ('??'),
    [best_for] NVARCHAR(MAX) NULL DEFAULT ('[]'),
    [strong_signals] NVARCHAR(MAX) NULL DEFAULT ('[]'),
    [weak_signals] NVARCHAR(MAX) NULL DEFAULT ('[]'),
    [not_for] NVARCHAR(MAX) NULL DEFAULT ('[]'),
    [roles] NVARCHAR(MAX) NULL DEFAULT ('[]'),
    [output_type] NVARCHAR(255) NULL DEFAULT (''),
    [is_internal] INT NULL DEFAULT ((0)),
    [raw_data] NVARCHAR(MAX) NULL DEFAULT ('{}'),
    [created_at] NVARCHAR(50) NULL,
    [updated_at] NVARCHAR(50) NULL,
    [source] NVARCHAR(50) NULL DEFAULT ('manual'),
    CONSTRAINT [PK__register__3213E83FFE1D27E5] PRIMARY KEY CLUSTERED ([id] ASC),
    CONSTRAINT [UQ__register__07C78DB817E9C686] UNIQUE NONCLUSTERED ([tool_name] ASC)
);

CREATE TABLE [dbo].[scenario_suggestions] (
    [id] NVARCHAR(36) NOT NULL,
    [title] NVARCHAR(500) NOT NULL,
    [mega_group] NVARCHAR(255) NOT NULL,
    [category] NVARCHAR(255) NULL DEFAULT (''),
    [persona] NVARCHAR(255) NULL DEFAULT (''),
    [activate_phase] NVARCHAR(255) NULL DEFAULT (''),
    [scenario] NVARCHAR(MAX) NOT NULL,
    [submitted_by] NVARCHAR(255) NULL DEFAULT (''),
    [submitted_at] NVARCHAR(50) NOT NULL,
    [status] NVARCHAR(50) NULL DEFAULT ('pending'),
    [admin_note] NVARCHAR(MAX) NULL DEFAULT (''),
    [reviewed_at] NVARCHAR(50) NULL DEFAULT (''),
    CONSTRAINT [PK__scenario__3213E83F78584F80] PRIMARY KEY CLUSTERED ([id] ASC)
);

CREATE TABLE [dbo].[scenarios] (
    [id] NVARCHAR(64) NOT NULL,
    [mega_group] NVARCHAR(255) NULL DEFAULT (''),
    [category] NVARCHAR(255) NULL DEFAULT (''),
    [phase] NVARCHAR(255) NULL DEFAULT (''),
    [title] NVARCHAR(500) NULL DEFAULT (''),
    [persona] NVARCHAR(255) NULL DEFAULT (''),
    [scenario] NVARCHAR(MAX) NULL DEFAULT (''),
    [task_type] NVARCHAR(255) NULL DEFAULT (''),
    [source] NVARCHAR(50) NULL DEFAULT ('excel'),
    [created_at] NVARCHAR(50) NULL DEFAULT (''),
    [summary] NVARCHAR(MAX) NULL DEFAULT (''),
    [is_tested] INT NULL DEFAULT ((0)),
    CONSTRAINT [PK__scenario__3213E83F97661652] PRIMARY KEY CLUSTERED ([id] ASC)
);

CREATE TABLE [dbo].[technical_feedbacks] (
    [id] NVARCHAR(64) NOT NULL,
    [feedback_id] NVARCHAR(64) NULL DEFAULT (''),
    [problem_title] NVARCHAR(500) NOT NULL,
    [problem_desc] NVARCHAR(MAX) NULL DEFAULT (''),
    [category] NVARCHAR(100) NULL DEFAULT (''),
    [status] NVARCHAR(50) NOT NULL DEFAULT ('pending'),
    [affected_count] INT NOT NULL DEFAULT ((1)),
    [reporter_emails] NVARCHAR(MAX) NULL DEFAULT ('[]'),
    [first_reported] NVARCHAR(50) NULL DEFAULT (''),
    [last_reported] NVARCHAR(50) NULL DEFAULT (''),
    [resolved_at] NVARCHAR(50) NULL DEFAULT (''),
    [admin_note] NVARCHAR(MAX) NULL DEFAULT (''),
    [created_at] NVARCHAR(50) NULL DEFAULT (''),
    [updated_at] NVARCHAR(50) NULL DEFAULT (''),
    [feature_area] NVARCHAR(100) NULL DEFAULT (''),
    CONSTRAINT [PK__technica__3213E83FED97A761] PRIMARY KEY CLUSTERED ([id] ASC)
);

CREATE TABLE [dbo].[tool_change_log] (
    [id] NVARCHAR(36) NOT NULL,
    [tool_name] NVARCHAR(255) NOT NULL,
    [action] NVARCHAR(50) NOT NULL,
    [changed_fields] NVARCHAR(MAX) NULL DEFAULT ('{}'),
    [changed_by] NVARCHAR(255) NULL DEFAULT ('admin'),
    [note] NVARCHAR(MAX) NULL DEFAULT (''),
    [created_at] NVARCHAR(50) NULL,
    CONSTRAINT [PK__tool_cha__3213E83FCF8F0B5D] PRIMARY KEY CLUSTERED ([id] ASC)
);

CREATE TABLE [dbo].[user_saved_scenarios] (
    [id] NVARCHAR(64) NOT NULL,
    [user_email] NVARCHAR(255) NOT NULL,
    [title] NVARCHAR(500) NOT NULL,
    [scenario] NVARCHAR(MAX) NULL DEFAULT (''),
    [persona] NVARCHAR(255) NULL DEFAULT (''),
    [mega_group] NVARCHAR(255) NULL DEFAULT (''),
    [category] NVARCHAR(255) NULL DEFAULT (''),
    [saved_at] NVARCHAR(50) NULL DEFAULT (''),
    CONSTRAINT [PK__user_sav__3213E83FE4A2024E] PRIMARY KEY CLUSTERED ([id] ASC),
    CONSTRAINT [uq_user_saved_scenario] UNIQUE NONCLUSTERED ([user_email] ASC, [title] ASC)
);

CREATE TABLE [dbo].[UserDefaultRole] (
    [id] INT IDENTITY(1,1) NOT NULL,
    [user_email] NVARCHAR(255) NOT NULL,
    [default_role] NVARCHAR(255) NOT NULL DEFAULT (''),
    [created_at] NVARCHAR(50) NULL,
    [updated_at] NVARCHAR(50) NULL,
    [tool_recommendation] BIT NULL DEFAULT ((1)),
    CONSTRAINT [PK__UserDefa__3213E83FACAA34EF] PRIMARY KEY CLUSTERED ([id] ASC),
    CONSTRAINT [uq_user_default_role] UNIQUE NONCLUSTERED ([user_email] ASC)
);

CREATE TABLE [dbo].[users] (
    [id] NVARCHAR(36) NOT NULL,
    [email] NVARCHAR(255) NOT NULL,
    [full_name] NVARCHAR(255) NULL DEFAULT (''),
    [role] NVARCHAR(255) NULL DEFAULT ('general'),
    [department] NVARCHAR(255) NULL DEFAULT (''),
    [is_active] INT NULL DEFAULT ((1)),
    [created_at] NVARCHAR(50) NULL,
    [last_login] NVARCHAR(50) NULL,
    CONSTRAINT [PK__users__3213E83FB8AADDCC] PRIMARY KEY CLUSTERED ([id] ASC),
    CONSTRAINT [UQ__users__AB6E616413321ECD] UNIQUE NONCLUSTERED ([email] ASC)
);

CREATE TABLE [dbo].[UserToolAccess] (
    [id] NVARCHAR(64) NOT NULL,
    [user_email] NVARCHAR(255) NOT NULL,
    [tool_name] NVARCHAR(255) NOT NULL,
    [has_access] BIT NOT NULL DEFAULT ((0)),
    [created_at] NVARCHAR(50) NULL,
    [updated_at] NVARCHAR(50) NULL,
    CONSTRAINT [PK__UserTool__3213E83FA4098685] PRIMARY KEY CLUSTERED ([id] ASC),
    CONSTRAINT [uq_user_tool_access] UNIQUE NONCLUSTERED ([user_email] ASC, [tool_name] ASC)
);
