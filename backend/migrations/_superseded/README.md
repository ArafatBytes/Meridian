# Superseded migrations (pre-S01)

These are the incremental SQL files used before the fresh-start schema. They are
kept for reference only.

**Do not run them.** `create_users_table.sql` in particular defines a
`public.users` with `name`/`avatar` columns that conflict with
`backend/app/models/user.py` (which expects `full_name`, `password_hash`,
`phone`, `hot_words`), and creates a `profile-pictures` storage bucket that the
app never uses — it uploads to a bucket named `avatars`.

Use [`../supabase/SCHEMA.sql`](../supabase/SCHEMA.sql) instead. `RESET.sql`
already cleans up the artifacts these files left behind.
