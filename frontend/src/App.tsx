import { BrowserRouter } from 'react-router-dom'
import { AuthProvider } from './auth/AuthContext'
import AppRoutes from './routes'
import { ThemeProvider } from './components/theme-provider'
import { Toaster } from "@/components/ui/sonner"

export default function App() {
  return (
    <ThemeProvider defaultTheme="system" storageKey="vite-ui-theme">
      <AuthProvider>
        <BrowserRouter>
          <AppRoutes />
        </BrowserRouter>
        <Toaster />
      </AuthProvider>
    </ThemeProvider>
  )
}

