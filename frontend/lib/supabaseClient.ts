/**
 * Supabase client for the browser. This is the ONLY thing that talks to
 * Supabase Auth directly (login, logout, session/token refresh). Every
 * other data operation goes through our FastAPI backend, which verifies
 * the resulting JWT itself — the frontend never queries Postgres directly.
 */
import { createClient } from "@supabase/supabase-js";

const supabaseUrl = process.env.NEXT_PUBLIC_SUPABASE_URL!;
const supabaseAnonKey = process.env.NEXT_PUBLIC_SUPABASE_ANON_KEY!;

if (!supabaseUrl || !supabaseAnonKey) {
  // Fail loudly at build/dev time rather than surfacing a cryptic runtime
  // error the first time someone tries to log in.
  console.error(
    "Missing NEXT_PUBLIC_SUPABASE_URL or NEXT_PUBLIC_SUPABASE_ANON_KEY. Check your .env.local file."
  );
}

export const supabase = createClient(supabaseUrl, supabaseAnonKey, {
  auth: {
    persistSession: true,
    autoRefreshToken: true,
    detectSessionInUrl: true,
  },
});
