import { useState, useEffect, useCallback } from 'react';
import { auth } from '../lib/auth';

export interface Lock {
    user_id: string;
    timestamp: number;
}

export interface UseLocksReturn {
    locks: Record<string, Lock>;
    isLockedByOther: (resourceId: string) => boolean;
    takeControl: (resourceId: string, userId: string) => Promise<boolean>;
    releaseControl: (resourceId: string, userId: string) => Promise<boolean>;
    loading: boolean;
    error: string | null;
}

export function useLocks(): UseLocksReturn {
    const [locks, setLocks] = useState<Record<string, Lock>>({});
    const [loading, setLoading] = useState(true);
    const [error, setError] = useState<string | null>(null);

    const apiUrl = process.env.NEXT_PUBLIC_ORCHESTRATION_HTTP || 'http://localhost:18010';

    const fetchLocks = useCallback(async () => {
        try {
            const res = await auth.fetch(`${apiUrl}/api/v1/collaboration/locks`);
            if (!res.ok) throw new Error('Failed to fetch locks');
            const data = await res.json();
            setLocks(data.locks);
            setError(null);
        } catch (err: any) {
            setError(err.message);
        } finally {
            setLoading(false);
        }
    }, [apiUrl]);

    useEffect(() => {
        fetchLocks();
        const interval = setInterval(fetchLocks, 2000); // Poll for now, in real pro app we'd use the WS
        return () => clearInterval(interval);
    }, [fetchLocks]);

    const isLockedByOther = (resourceId: string) => {
        const lock = locks[resourceId];
        if (!lock) return false;
        // In a real app we'd have the current user's ID
        const currentUserId = typeof window !== 'undefined' ? window.localStorage.getItem('sc-user-id') : null;
        return lock.user_id !== currentUserId;
    };

    const takeControl = async (resourceId: string, userId: string) => {
        try {
            const res = await auth.fetch(`${apiUrl}/api/v1/collaboration/lock`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ resource_id: resourceId, user_id: userId }),
            });
            if (!res.ok) {
                if (res.status === 423) {
                    setError("Locked by another user");
                    return false;
                }
                throw new Error('Lock acquisition failed');
            }
            const data = await res.json();
            setLocks(data.locks);
            return true;
        } catch (err: any) {
            setError(err.message);
            return false;
        }
    };

    const releaseControl = async (resourceId: string, userId: string) => {
        try {
            const res = await auth.fetch(`${apiUrl}/api/v1/collaboration/lock`, {
                method: 'DELETE',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ resource_id: resourceId, user_id: userId }),
            });
            if (!res.ok) throw new Error('Lock release failed');
            const data = await res.json();
            setLocks(data.locks);
            return true;
        } catch (err: any) {
            setError(err.message);
            return false;
        }
    };

    return { locks, isLockedByOther, takeControl, releaseControl, loading, error };
}
