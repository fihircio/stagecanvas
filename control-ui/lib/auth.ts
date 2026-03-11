/**
 * SC-113 - Auth Utility
 * Handles JWT storage and authenticated fetch wrapping.
 */

import { useState, useCallback } from 'react'; // Added import for useState and useCallback

const TOKEN_KEY = 'sc-auth-token';
const USER_KEY = 'sc-user-info';

export interface UserInfo {
    username: string;
    role: 'viewer' | 'operator' | 'designer' | 'admin';
}

export const auth = {
    setToken: (token: string) => {
        if (typeof window !== 'undefined') {
            localStorage.setItem(TOKEN_KEY, token);
        }
    },

    getToken: () => {
        if (typeof window !== 'undefined') {
            return localStorage.getItem(TOKEN_KEY);
        }
        return null;
    },

    setUser: (user: UserInfo) => {
        if (typeof window !== 'undefined') {
            localStorage.setItem(USER_KEY, JSON.stringify(user));
        }
    },

    getUser: (): UserInfo | null => {
        if (typeof window !== 'undefined') {
            const data = localStorage.getItem(USER_KEY);
            return data ? JSON.parse(data) : null;
        }
        return null;
    },

    logout: () => {
        if (typeof window !== 'undefined') {
            localStorage.removeItem(TOKEN_KEY);
            localStorage.removeItem(USER_KEY);
        }
    },

    isLoggedIn: () => {
        return !!auth.getToken();
    },

    /**
     * Reusable fetch wrapper that injects Authorization header.
     */
    fetch: async (url: string, options: RequestInit = {}) => {
        const token = auth.getToken();
        const headers: Record<string, string> = {
            ...(options.headers as Record<string, string>),
            ...(token ? { 'Authorization': `Bearer ${token}` } : {}),
        };
        if (!headers['Content-Type']) {
            headers['Content-Type'] = 'application/json';
        }

        const response = await fetch(url, { ...options, headers });
        
        if (response.status === 401) {
            // Auto-logout on unauthorized
            auth.logout();
            if (typeof window !== 'undefined' && window.location.pathname !== '/') {
                window.location.href = '/';
            }
        }
        
        return response;
    }
};
