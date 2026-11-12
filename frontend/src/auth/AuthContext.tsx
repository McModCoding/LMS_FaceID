import React, { createContext, useContext, useState, useEffect } from 'react'
import { User } from '../types/user'
import api from '../api/client'

interface AuthContextType {
  user: User | null
  token: string | null
  isAuthenticated: boolean
  isLoading: boolean
  login: (token: string, user: User) => void
  logout: () => void
  updateUser: (userPartial: Partial<User>) => void
}

const AuthContext = createContext<AuthContextType | undefined>(undefined)

export const AuthProvider: React.FC<{ children: React.ReactNode }> = ({ children }) => {
  const [user, setUser] = useState<User | null>(() => {
    const savedUser = localStorage.getItem('user')
    return savedUser ? JSON.parse(savedUser) : null
  })
  const [token, setToken] = useState<string | null>(() => localStorage.getItem('token'))
  const [isLoading, setIsLoading] = useState<boolean>(true)

  useEffect(() => {
    const fetchMe = async () => {
      if (token) {
        try {
          const response = await api.get('/auth/me')
          setUser(response.data)
          localStorage.setItem('user', JSON.stringify(response.data))
        } catch (error) {
          console.error('Failed to fetch user profile:', error)
          // Don't auto-logout if server error or offline, but clear if 401 (handled in client.ts)
        }
      }
      setIsLoading(false)
    }
    fetchMe()
  }, [token])

  const login = (newToken: string, newUser: User) => {
    setToken(newToken)
    setUser(newUser)
    localStorage.setItem('token', newToken)
    localStorage.setItem('user', JSON.stringify(newUser))
  }

  const logout = () => {
    setToken(null)
    setUser(null)
    localStorage.removeItem('token')
    localStorage.removeItem('user')
  }

  const updateUser = (userPartial: Partial<User>) => {
    setUser((prev) => {
      if (!prev) return null
      const updated = { ...prev, ...userPartial }
      localStorage.setItem('user', JSON.stringify(updated))
      return updated
    })
  }

  return (
    <AuthContext.Provider
      value={{
        user,
        token,
        isAuthenticated: !!token && !!user,
        isLoading,
        login,
        logout,
        updateUser,
      }}
    >
      {children}
    </AuthContext.Provider>
  )
}

// eslint-disable-next-line react-refresh/only-export-components
export const useAuth = (): AuthContextType => {
  const context = useContext(AuthContext)
  if (!context) {
    throw new Error('useAuth must be used within an AuthProvider')
  }
  return context
}
