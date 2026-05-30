import { createRootRouteWithContext, createRoute, createRouter, Navigate, Outlet, redirect } from '@tanstack/react-router'
import { AppShell } from '@/app/layout/AppShell'
import { normalizeActivitySearch } from '@/features/activity/filters/model'

type AppRouterContext = {
  app?: never
}

const rootRoute = createRootRouteWithContext<AppRouterContext>()({
  component: RootLayout,
  notFoundComponent: () => <Navigate to="/dashboard" replace />,
})

const indexRoute = createRoute({
  getParentRoute: () => rootRoute,
  path: '/',
  beforeLoad: () => {
    throw redirect({ to: '/dashboard', replace: true })
  },
})

const dashboardRoute = createRoute({
  getParentRoute: () => rootRoute,
  path: '/dashboard',
}).lazy(() => import('@/app/routes/dashboard.lazy').then((d) => d.Route))

const organizeRoute = createRoute({
  getParentRoute: () => rootRoute,
  path: '/organize',
}).lazy(() => import('@/app/routes/organize.lazy').then((d) => d.Route))

const servicesRoute = createRoute({
  getParentRoute: () => rootRoute,
  path: '/services',
}).lazy(() => import('@/app/routes/services.lazy').then((d) => d.Route))

const transferRoute = createRoute({
  getParentRoute: () => rootRoute,
  path: '/transfer',
}).lazy(() => import('@/app/routes/transfer.lazy').then((d) => d.Route))

const activityRoute = createRoute({
  getParentRoute: () => rootRoute,
  path: '/activity',
  validateSearch: normalizeActivitySearch,
}).lazy(() => import('@/app/routes/activity.lazy').then((d) => d.Route))

const rulesRoute = createRoute({
  getParentRoute: () => rootRoute,
  path: '/rules',
}).lazy(() => import('@/app/routes/rules.lazy').then((d) => d.Route))

const settingsRoute = createRoute({
  getParentRoute: () => rootRoute,
  path: '/settings',
}).lazy(() => import('@/app/routes/settings.lazy').then((d) => d.Route))

const helpRoute = createRoute({
  getParentRoute: () => rootRoute,
  path: '/help',
}).lazy(() => import('@/app/routes/help.lazy').then((d) => d.Route))

const routeTree = rootRoute.addChildren([
  indexRoute,
  dashboardRoute,
  organizeRoute,
  servicesRoute,
  transferRoute,
  activityRoute,
  rulesRoute,
  settingsRoute,
  helpRoute,
])

export function createOmediaRouter() {
  return createRouter({
    routeTree,
    context: {},
    defaultPreload: 'intent',
  })
}

export type OmediaRouter = ReturnType<typeof createOmediaRouter>

declare module '@tanstack/react-router' {
  interface Register {
    router: OmediaRouter
  }
}

function RootLayout() {
  return (
    <AppShell>
      <Outlet />
    </AppShell>
  )
}
