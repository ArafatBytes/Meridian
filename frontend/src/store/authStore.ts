import { create } from 'zustand';
import { User } from '../types';
import { AuthService } from '../services';

interface AuthState {
  user: User | null;
  isAuthenticated: boolean;
  isLoading: boolean;
  error: string | null;
  token: string | null;

  // Actions
  setUser: (user: User | null) => void;
  setLoading: (isLoading: boolean) => void;
  setError: (error: string | null) => void;
  login: (email: string, password: string) => Promise<void>;
  loginWithoutAuth: (email: string, password: string) => Promise<User>;
  register: (data: any) => Promise<void>;
  registerWithoutAuth: (data: any) => Promise<User>;
  setAuthenticated: (user: User) => void;
  logout: () => Promise<void>;
  initialize: () => Promise<void>;
  clearError: () => void;
}

export const useAuthStore = create<AuthState>(set => ({
  user: null,
  isAuthenticated: false,
  isLoading: false,
  error: null,
  token: null,

  setUser: user => set({ user, isAuthenticated: !!user }),

  setLoading: isLoading => set({ isLoading }),

  setError: error => set({ error }),

  clearError: () => set({ error: null }),

  login: async (email, password) => {
    try {
      set({ isLoading: true, error: null });
      const response = await AuthService.login({ email, password });
      set({
        user: response.user,
        token: response.tokens.accessToken,
        isAuthenticated: true,
        isLoading: false,
      });
    } catch (error: any) {
      set({
        error: error.message || 'Login failed',
        isLoading: false,
      });
      throw error;
    }
  },

  loginWithoutAuth: async (email, password) => {
    try {
      set({ error: null });
      const response = await AuthService.login({ email, password });
      set({ token: response.tokens.accessToken });
      return response.user;
    } catch (error: any) {
      set({
        error: error.message || 'Login failed',
      });
      throw error;
    }
  },

  register: async data => {
    try {
      set({ isLoading: true, error: null });
      const response = await AuthService.register(data);
      set({
        user: response.user,
        token: response.tokens.accessToken,
        isAuthenticated: true,
        isLoading: false,
      });
    } catch (error: any) {
      set({
        error: error.message || 'Registration failed',
        isLoading: false,
      });
      throw error;
    }
  },

  registerWithoutAuth: async data => {
    try {
      set({ error: null });
      const response = await AuthService.register(data);
      return response.user;
    } catch (error: any) {
      set({
        error: error.message || 'Registration failed',
      });
      throw error;
    }
  },

  setAuthenticated: user => {
    set({
      user,
      isAuthenticated: true,
      isLoading: false,
    });
  },

  logout: async () => {
    try {
      set({ isLoading: true });
      await AuthService.logout();
      set({
        user: null,
        token: null,
        isAuthenticated: false,
        isLoading: false,
        error: null,
      });
    } catch (error: any) {
      set({
        error: error.message || 'Logout failed',
        isLoading: false,
      });
      throw error;
    }
  },

  initialize: async () => {
    try {
      set({ isLoading: true });
      const user = await AuthService.getCurrentUser();
      const isAuthenticated = await AuthService.isAuthenticated();
      const token = await AuthService.getAuthToken();

      set({
        user,
        token,
        isAuthenticated,
        isLoading: false,
      });
    } catch (error: any) {
      set({
        user: null,
        token: null,
        isAuthenticated: false,
        isLoading: false,
        error: error.message,
      });
    }
  },
}));
