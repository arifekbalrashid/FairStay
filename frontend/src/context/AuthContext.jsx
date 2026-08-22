import { createContext, useState, useContext, useEffect } from 'react';

const AuthContext = createContext(null);

export function AuthProvider({ children }) {
  const [user, setUser] = useState(() => {
    const saved = localStorage.getItem('fairdeal_user');
    if (saved) return JSON.parse(saved);
    return null; // null means not logged in
  });

  useEffect(() => {
    if (user) {
      localStorage.setItem('fairdeal_user', JSON.stringify(user));
    } else {
      localStorage.removeItem('fairdeal_user');
    }
  }, [user]);

  const loginAsHost = () => {
    setUser({ role: 'host', id: 'host_demo_1' });
  };

  const loginAsGuest = () => {
    setUser({ role: 'guest', id: 'guest_demo_1' });
  };

  const logout = () => {
    setUser(null);
  };

  return (
    <AuthContext.Provider value={{ user, loginAsHost, loginAsGuest, logout }}>
      {children}
    </AuthContext.Provider>
  );
}

export function useAuth() {
  return useContext(AuthContext);
}
