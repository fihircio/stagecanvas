import { useState, useCallback, useEffect } from 'react';
import { auth, UserInfo } from '../lib/auth';

export interface UseAuthReturn {
    user: UserInfo | null;
    isLoggedIn: boolean;
    login: (username: string, password: string) => Promise<boolean>;
    logout: () => void;
    hasRole: (roles: UserInfo['role'][]) => boolean;
}

const ORCHESTRATION_HTTP = process.env.NEXT_PUBLIC_ORCHESTRATION_HTTP || 'http://localhost:18010';

export function useAuth(): UseAuthReturn {
    const [user, setUser] = useState<UserInfo | null>(auth.getUser());
    const [isLoggedIn, setIsLoggedIn] = useState(auth.isLoggedIn());

    const login = useCallback(async (username: string, password: string) => {
        try {
            const formData = new URLSearchParams();
            formData.append('username', username);
            formData.append('password', password);

            const res = await fetch(`${ORCHESTRATION_HTTP}/api/v1/auth/token`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/x-www-form-urlencoded' },
                body: formData,
            });

            if (!res.ok) throw new Error('Login failed');
            
            const data = await res.json();
            auth.setToken(data.access_token);
            
            // Decodes JWT (base64) for role/user info or fetch /me
            // Simplified: we assume the token payload has role, or we perform a second fetch.
            // For now, parse base64 payload:
            const payload = JSON.parse(atob(data.access_token.split('.')[1]));
            const loggedInUser: UserInfo = {
                username: payload.sub,
                role: payload.role as UserInfo['role'],
            };
            
            auth.setUser(loggedInUser);
            setUser(loggedInUser);
            setIsLoggedIn(true);
            return true;
        } catch (err) {
            console.error(err);
            return false;
        }
    }, []);

    const logout = useCallback(() => {
        auth.logout();
        setUser(null);
        setIsLoggedIn(false);
    }, []);

    const hasRole = useCallback((requiredRoles: UserInfo['role'][]) => {
        if (!user) return false;
        // Basic role hierarchy check
        const roleOrder: UserInfo['role'][] = ['admin', 'designer', 'operator', 'viewer'];
        const userLevel = roleOrder.indexOf(user.role);
        const minRequiredLevel = Math.min(...requiredRoles.map(r => roleOrder.indexOf(r)));
        
        return userLevel <= minRequiredLevel;
    }, [user]);

    return { user, isLoggedIn, login, logout, hasRole };
}
