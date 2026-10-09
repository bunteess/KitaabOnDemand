import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { createBrowserRouter, Navigate, RouterProvider, type RouteObject } from "react-router";
import { AuthProvider } from "./auth/AuthContext";
import { RequireRole } from "./auth/RequireRole";
import { ADMIN_NAV, Shell, VENDOR_NAV } from "./layout/Shell";
import { AuditPage } from "./pages/admin/AuditPage";
import { CitiesPage } from "./pages/admin/CitiesPage";
import { CodPage, PayoutsPage, RefundsPage, RevenuePage } from "./pages/admin/FinancePages";
import { CustomerDetailPage, CustomersPage } from "./pages/admin/CustomersPages";
import { OrderDetailPage } from "./pages/admin/OrderDetailPage";
import { OrdersPage } from "./pages/admin/OrdersPage";
import { PricingPage } from "./pages/admin/PricingPage";
import { SettingsPage } from "./pages/admin/SettingsPage";
import { StaffPage } from "./pages/admin/StaffPage";
import { VendorsPage } from "./pages/admin/VendorsPage";
import { LoginPage } from "./pages/LoginPage";
import { VendorOrderPage } from "./pages/vendor/VendorOrderPage";
import { VendorQueuePage } from "./pages/vendor/VendorQueuePage";

export const routes: RouteObject[] = [
  { path: "/login", element: <LoginPage /> },
  {
    path: "/admin",
    element: (
      <RequireRole role="ADMIN">
        <Shell title="Admin" nav={ADMIN_NAV} />
      </RequireRole>
    ),
    children: [
      { index: true, element: <OrdersPage /> },
      { path: "orders/:orderId", element: <OrderDetailPage /> },
      { path: "vendors", element: <VendorsPage /> },
      { path: "customers", element: <CustomersPage /> },
      { path: "customers/:userId", element: <CustomerDetailPage /> },
      { path: "staff", element: <StaffPage /> },
      { path: "pricing", element: <PricingPage /> },
      { path: "cities", element: <CitiesPage /> },
      { path: "finance/revenue", element: <RevenuePage /> },
      { path: "finance/cod", element: <CodPage /> },
      { path: "finance/payouts", element: <PayoutsPage /> },
      { path: "finance/refunds", element: <RefundsPage /> },
      { path: "audit", element: <AuditPage /> },
      { path: "settings", element: <SettingsPage /> },
    ],
  },
  {
    path: "/vendor",
    element: (
      <RequireRole role="VENDOR">
        <Shell title="Vendor" nav={VENDOR_NAV} />
      </RequireRole>
    ),
    children: [
      { index: true, element: <VendorQueuePage /> },
      { path: "orders/:orderId", element: <VendorOrderPage /> },
    ],
  },
  { path: "*", element: <Navigate to="/login" replace /> },
];

export function createQueryClient() {
  return new QueryClient({
    defaultOptions: {
      queries: { retry: 1, staleTime: 15_000, refetchOnWindowFocus: false },
    },
  });
}

const router = createBrowserRouter(routes);
const queryClient = createQueryClient();

export function App() {
  return (
    <QueryClientProvider client={queryClient}>
      <AuthProvider>
        <RouterProvider router={router} />
      </AuthProvider>
    </QueryClientProvider>
  );
}
