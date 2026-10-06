import { supabase } from '../lib/supabase';
import * as SecureStore from 'expo-secure-store';
import { STORAGE_KEYS } from '../constants';
import {
  AuthResponse,
  LoginRequest,
  RegisterRequest,
  User,
  AuthTokens,
} from '../types';

class AuthService {
  async login(credentials: LoginRequest): Promise<AuthResponse> {
    try {
      const { data, error } = await supabase.auth.signInWithPassword({
        email: credentials.email,
        password: credentials.password,
      });

      if (error) {
        throw new Error(error.message);
      }

      if (!data.user || !data.session) {
        throw new Error('Login failed');
      }

      // Get user profile from profiles table
      const { data: profile, error: profileError } = await supabase
        .from('profiles')
        .select('*')
        .eq('id', data.user.id)
        .maybeSingle(); // Use maybeSingle() instead of single() to handle no rows

      if (profileError) {
        console.error('Profile fetch error:', profileError);
      }

      // If profile doesn't exist, create it
      if (!profile) {
        console.log('Profile not found, creating one...');
        const { error: createError } = await supabase.from('profiles').insert({
          id: data.user.id,
          email: data.user.email!,
          name: data.user.user_metadata?.name || data.user.email!.split('@')[0],
          phone: data.user.user_metadata?.phone || null,
          avatar_url: null,
          created_at: new Date().toISOString(),
          updated_at: new Date().toISOString(),
        });

        if (createError) {
          console.error('Failed to create profile:', createError);
        }
      }

      const authResponse: AuthResponse = {
        user: {
          id: data.user.id,
          email: data.user.email!,
          name:
            profile?.name ||
            data.user.user_metadata?.name ||
            data.user.email!.split('@')[0],
          phone: profile?.phone || data.user.user_metadata?.phone || null,
          avatar_url: profile?.avatar_url || null,
          createdAt: data.user.created_at,
          updatedAt: data.user.updated_at || data.user.created_at,
        },
        tokens: {
          accessToken: data.session.access_token,
          refreshToken: data.session.refresh_token,
        },
      };

      await this.saveAuthData(authResponse);
      return authResponse;
    } catch (error: any) {
      throw new Error(error.message || 'Login failed');
    }
  }

  async register(data: RegisterRequest): Promise<AuthResponse> {
    try {
      // Sign up with Supabase Auth
      const { data: authData, error: signUpError } = await supabase.auth.signUp(
        {
          email: data.email,
          password: data.password,
          options: {
            data: {
              name: data.name,
              phone: data.phone,
            },
          },
        },
      );

      if (signUpError) {
        throw new Error(signUpError.message);
      }

      if (!authData.user || !authData.session) {
        throw new Error('Registration failed');
      }

      // Create profile in profiles table (use upsert to handle existing profiles)
      const { error: profileError } = await supabase.from('profiles').upsert(
        {
          id: authData.user.id,
          email: data.email,
          name: data.name,
          phone: data.phone,
          avatar_url: null,
          created_at: new Date().toISOString(),
          updated_at: new Date().toISOString(),
        },
        {
          onConflict: 'id',
        },
      );

      if (profileError) {
        console.error('Profile creation error:', profileError);
        // Don't throw error, continue with registration
      }

      const authResponse: AuthResponse = {
        user: {
          id: authData.user.id,
          email: authData.user.email!,
          name: data.name,
          phone: data.phone,
          avatar_url: null,
          createdAt: authData.user.created_at,
          updatedAt: authData.user.updated_at || authData.user.created_at,
        },
        tokens: {
          accessToken: authData.session.access_token,
          refreshToken: authData.session.refresh_token,
        },
      };

      await this.saveAuthData(authResponse);
      return authResponse;
    } catch (error: any) {
      throw new Error(error.message || 'Registration failed');
    }
  }

  async logout(): Promise<void> {
    try {
      await supabase.auth.signOut();
    } catch (error) {
      console.error('Logout error:', error);
    } finally {
      await this.clearAuthData();
    }
  }

  async getCurrentUser(): Promise<User | null> {
    try {
      // First try to get from SecureStore cache
      const userData = await SecureStore.getItemAsync(STORAGE_KEYS.USER_DATA);
      if (userData) {
        return JSON.parse(userData);
      }

      // If not in cache, get from Supabase
      const {
        data: { user },
        error,
      } = await supabase.auth.getUser();
      if (error || !user) {
        return null;
      }

      // Get profile data
      const { data: profile } = await supabase
        .from('profiles')
        .select('*')
        .eq('id', user.id)
        .single();

      const userData2: User = {
        id: user.id,
        email: user.email!,
        name: profile?.name || user.email!.split('@')[0],
        phone: profile?.phone || null,
        avatar_url: profile?.avatar_url || null,
        createdAt: user.created_at,
        updatedAt: user.updated_at || user.created_at,
      };

      // Cache it
      await SecureStore.setItemAsync(
        STORAGE_KEYS.USER_DATA,
        JSON.stringify(userData2),
      );

      return userData2;
    } catch (error) {
      console.error('Error getting current user:', error);
      return null;
    }
  }

  async getAuthToken(): Promise<string | null> {
    try {
      // Get from SecureStore cache
      const cachedToken = await SecureStore.getItemAsync(
        STORAGE_KEYS.AUTH_TOKEN,
      );
      if (cachedToken) {
        return cachedToken;
      }

      // Get fresh session from Supabase
      const {
        data: { session },
      } = await supabase.auth.getSession();
      if (session?.access_token) {
        await SecureStore.setItemAsync(
          STORAGE_KEYS.AUTH_TOKEN,
          session.access_token,
        );
        return session.access_token;
      }

      return null;
    } catch (error) {
      console.error('Error getting auth token:', error);
      return null;
    }
  }

  async isAuthenticated(): Promise<boolean> {
    try {
      const {
        data: { session },
      } = await supabase.auth.getSession();
      return !!session;
    } catch (error) {
      return false;
    }
  }

  async getSession() {
    try {
      const {
        data: { session },
        error,
      } = await supabase.auth.getSession();
      if (error) throw error;
      return session;
    } catch (error) {
      console.error('Error getting session:', error);
      return null;
    }
  }

  private async saveAuthData(authResponse: AuthResponse): Promise<void> {
    const { user, tokens } = authResponse;

    await SecureStore.setItemAsync(STORAGE_KEYS.AUTH_TOKEN, tokens.accessToken);
    await SecureStore.setItemAsync(
      STORAGE_KEYS.REFRESH_TOKEN,
      tokens.refreshToken,
    );
    await SecureStore.setItemAsync(
      STORAGE_KEYS.USER_DATA,
      JSON.stringify(user),
    );
  }

  private async clearAuthData(): Promise<void> {
    await SecureStore.deleteItemAsync(STORAGE_KEYS.AUTH_TOKEN);
    await SecureStore.deleteItemAsync(STORAGE_KEYS.REFRESH_TOKEN);
    await SecureStore.deleteItemAsync(STORAGE_KEYS.USER_DATA);
  }

  async refreshToken(): Promise<AuthTokens | null> {
    try {
      const {
        data: { session },
        error,
      } = await supabase.auth.refreshSession();

      if (error || !session) {
        throw new Error('Failed to refresh session');
      }

      const tokens: AuthTokens = {
        accessToken: session.access_token,
        refreshToken: session.refresh_token,
      };

      await SecureStore.setItemAsync(
        STORAGE_KEYS.AUTH_TOKEN,
        tokens.accessToken,
      );
      await SecureStore.setItemAsync(
        STORAGE_KEYS.REFRESH_TOKEN,
        tokens.refreshToken,
      );

      return tokens;
    } catch (error) {
      await this.clearAuthData();
      throw error;
    }
  }
}

export default new AuthService();
