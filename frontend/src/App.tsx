import React, { useState, useEffect, useCallback } from 'react';
import { api } from './lib/api';
import { AgentStatus, Invoice, Payment } from './types';
import { Sidebar } from './components/layout/Sidebar';
import { DemoResetProvider } from './components/layout/DemoReset';
import { ToastProvider, useToast } from './components/ui/Toast';
import { NewInvoiceModal } from './components/modals/NewInvoiceModal';
import { RecordPaymentModal } from './components/modals/RecordPaymentModal';
import { AddClientModal } from './components/modals/AddClientModal';
import { DocumentViewerModal, ViewedDocument } from './components/modals/DocumentViewerModal';

// Pages
import { OverviewPage } from './pages/OverviewPage';
import { AgentPage, forgetConversation } from './pages/AgentPage';
import { InvoicesPage } from './pages/InvoicesPage';
import { InvoiceDetailPage } from './pages/InvoiceDetailPage';
import { ClientsPage } from './pages/ClientsPage';
import { ClientDetailPage } from './pages/ClientDetailPage';
import { PaymentsPage } from './pages/PaymentsPage';
import { OverduePage } from './pages/OverduePage';
import { RemindersPage } from './pages/RemindersPage';
import { ReportsPage } from './pages/ReportsPage';
import { IconMenu } from './components/Icons';

// How often the sidebar re-reads provider status. Status is a free local
// check on the server — it never calls a model.
const STATUS_POLL_MS = 30_000;

function MainApp() {
  const { addToast } = useToast();
  const [currentPath, setCurrentPath] = useState<string>('/');
  const [isMobileNavOpen, setIsMobileNavOpen] = useState<boolean>(false);
  const [agentStatus, setAgentStatus] = useState<AgentStatus | null>(null);
  const [backendOnline, setBackendOnline] = useState(true);

  const refreshAgentStatus = useCallback(async () => {
    try {
      setAgentStatus(await api.getAgentStatus());
      setBackendOnline(true);
    } catch {
      setBackendOnline(false);
    }
  }, []);

  useEffect(() => {
    refreshAgentStatus();
    const timer = window.setInterval(refreshAgentStatus, STATUS_POLL_MS);
    return () => window.clearInterval(timer);
  }, [refreshAgentStatus]);

  // Prefilled agent query passed from other pages (e.g. Overview search input)
  const [prefilledAgentQuery, setPrefilledAgentQuery] = useState<string>('');

  // Modals state
  const [isNewInvoiceOpen, setIsNewInvoiceOpen] = useState(false);
  const [defaultNewInvoiceClientId, setDefaultNewInvoiceClientId] = useState<number | undefined>();
  const [recordPaymentInvoice, setRecordPaymentInvoice] = useState<Invoice | null>(null);
  const [isAddClientOpen, setIsAddClientOpen] = useState(false);
  const [documentViewer, setDocumentViewer] = useState<ViewedDocument>(null);
  const [flashInvoiceId, setFlashInvoiceId] = useState<string | number | null>(null);
  const [flashPaymentId, setFlashPaymentId] = useState<string | number | null>(null);

  // Key to force refresh of lists when data mutates
  const [refreshKey, setRefreshKey] = useState(0);
  const triggerRefresh = () => setRefreshKey((k) => k + 1);
  // The agent page keeps its conversation across ledger changes; only a demo
  // reset replaces it.
  const [agentKey, setAgentKey] = useState(0);

  // Sync browser back/forward or simple URL hash
  useEffect(() => {
    const handlePopState = () => {
      const hash = window.location.hash.replace('#', '') || '/';
      setCurrentPath(hash);
    };
    if (window.location.hash) {
      handlePopState();
    }
    window.addEventListener('popstate', handlePopState);
    return () => window.removeEventListener('popstate', handlePopState);
  }, []);

  const navigate = (path: string) => {
    if ('startViewTransition' in document && typeof (document as any).startViewTransition === 'function') {
      const transition = (document as any).startViewTransition(() => {
        setCurrentPath(path);
        window.location.hash = path;
        window.scrollTo({ top: 0, behavior: 'instant' });
      });
      // Navigating again mid-animation aborts the first transition. The page
      // still changes; only the animation is skipped, so this is not an error.
      const ignore = () => undefined;
      transition.ready?.catch(ignore);
      transition.finished?.catch(ignore);
    } else {
      setCurrentPath(path);
      window.location.hash = path;
      window.scrollTo({ top: 0, behavior: 'instant' });
    }
  };

  const handleOpenInvoicePdf = (invoice: Invoice) => {
    setDocumentViewer({
      type: 'invoice',
      invoiceId: invoice.invoice_id,
      number: invoice.invoice_number,
      clientName: invoice.client_name,
    });
  };

  const handleOpenReceiptPdf = (payment: Payment) => {
    setDocumentViewer({
      type: 'receipt',
      paymentId: payment.payment_id,
      number: payment.receipt_number,
      clientName: payment.client_name,
    });
  };

  const closeDocument = () => {
    // Opening a receipt for the first time issues its number; refresh so the
    // ledger shows it.
    if (documentViewer?.type === 'receipt' && !documentViewer.number) triggerRefresh();
    setDocumentViewer(null);
  };

  // Router matching
  const renderCurrentView = () => {
    // /invoices/:id
    if (currentPath.startsWith('/invoices/')) {
      const idStr = currentPath.replace('/invoices/', '');
      const id = parseInt(idStr, 10);
      if (!isNaN(id)) {
        return (
          <InvoiceDetailPage
            key={`${id}-${refreshKey}`}
            invoiceId={id}
            onNavigate={navigate}
            onOpenRecordPayment={(inv) => setRecordPaymentInvoice(inv)}
            onViewPdf={handleOpenInvoicePdf}
            onViewReceiptPdf={handleOpenReceiptPdf}
          />
        );
      }
    }

    // /clients/:id
    if (currentPath.startsWith('/clients/')) {
      const idStr = currentPath.replace('/clients/', '');
      const id = parseInt(idStr, 10);
      if (!isNaN(id)) {
        return (
          <ClientDetailPage
            key={`${id}-${refreshKey}`}
            clientId={id}
            onNavigate={navigate}
            onOpenNewInvoice={(cId) => {
              setDefaultNewInvoiceClientId(cId);
              setIsNewInvoiceOpen(true);
            }}
            onOpenRecordPayment={(inv) => setRecordPaymentInvoice(inv)}
            onViewPdf={handleOpenInvoicePdf}
            onViewReceiptPdf={handleOpenReceiptPdf}
          />
        );
      }
    }

    switch (currentPath) {
      case '/agent':
        return (
          <AgentPage
            key={`agent-${agentKey}`}
            onNavigate={navigate}
            agentStatus={agentStatus}
            backendOnline={backendOnline}
            prefilledQuery={prefilledAgentQuery}
            onClearPrefilled={() => setPrefilledAgentQuery('')}
            onViewInvoicePdf={handleOpenInvoicePdf}
            onViewReceiptPdf={handleOpenReceiptPdf}
            onLedgerChanged={() => {
              refreshAgentStatus();
            }}
          />
        );
      case '/invoices':
        return (
          <InvoicesPage
            key={refreshKey}
            onNavigate={navigate}
            onOpenNewInvoice={() => {
              setDefaultNewInvoiceClientId(undefined);
              setIsNewInvoiceOpen(true);
            }}
            onOpenRecordPayment={(inv) => setRecordPaymentInvoice(inv)}
            onViewPdf={handleOpenInvoicePdf}
            flashInvoiceId={flashInvoiceId}
          />
        );
      case '/clients':
        return (
          <ClientsPage
            key={refreshKey}
            onNavigate={navigate}
            onOpenAddClient={() => setIsAddClientOpen(true)}
          />
        );
      case '/payments':
        return (
          <PaymentsPage
            key={refreshKey}
            onNavigate={navigate}
            onViewReceiptPdf={handleOpenReceiptPdf}
            flashPaymentId={flashPaymentId}
          />
        );
      case '/overdue':
        return (
          <OverduePage
            key={refreshKey}
            onNavigate={navigate}
            onOpenRecordPayment={(inv) => setRecordPaymentInvoice(inv)}
          />
        );
      case '/reminders':
        return <RemindersPage key={refreshKey} onNavigate={navigate} />;
      case '/reports':
        return <ReportsPage key={refreshKey} onNavigate={navigate} />;
      case '/':
      default:
        return (
          <OverviewPage
            key={refreshKey}
            onNavigate={navigate}
            onOpenRecordPayment={(inv) => setRecordPaymentInvoice(inv)}
            onPrefillAgent={(text) => {
              setPrefilledAgentQuery(text);
              navigate('/agent');
            }}
          />
        );
    }
  };

  const handleDemoReset = () => {
    forgetConversation();
    setAgentKey((k) => k + 1); // remount the agent page with an empty conversation
    setDocumentViewer(null);
    setRecordPaymentInvoice(null);
    triggerRefresh();
    refreshAgentStatus();
    addToast('Demo data reset — the sample ledger is back to where it started');
  };

  return (
    <DemoResetProvider onReset={handleDemoReset} onError={addToast}>
    <div
      className="min-h-screen flex flex-col lg:flex-row"
      style={{ backgroundColor: 'var(--canvas)' }}
    >
      {/* Mobile Top Bar (visible only below lg) */}
      <div
        className="flex items-center justify-between px-4 py-3 border-b lg:hidden"
        style={{
          backgroundColor: 'var(--surface)',
          borderColor: 'var(--line)',
        }}
      >
        <div className="flex items-center gap-2.5" onClick={() => navigate('/')}>
          <div
            className="flex items-center justify-center w-[26px] h-[26px] rounded-[6px] text-white font-[700] text-[14px]"
            style={{ background: 'linear-gradient(160deg, #635bff, #4b45c6)' }}
          >
            F
          </div>
          <span className="text-[14px] font-[600]" style={{ color: 'var(--ink)' }}>
            FreelanceFlow
          </span>
        </div>
        <button
          type="button"
          className="p-2 rounded-[6px] hover:bg-[var(--surface-sunken)]"
          onClick={() => setIsMobileNavOpen(true)}
          aria-label="Open navigation menu"
        >
          <IconMenu size={18} />
        </button>
      </div>

      {/* Sidebar: Fixed 232px width per Section 4 */}
      <Sidebar
        currentPath={currentPath}
        onNavigate={navigate}
        agentStatus={agentStatus}
        backendOnline={backendOnline}
        isMobileOpen={isMobileNavOpen}
        onCloseMobile={() => setIsMobileNavOpen(false)}
      />

      {/* Main Content Column: gutters 28px top, 34px sides, max-width 1240px per Section 4 */}
      <main
        className={`flex-1 min-w-0 ${
          currentPath === '/agent'
            ? 'h-[100dvh] flex flex-col overflow-hidden p-0'
            : 'overflow-y-auto px-[20px] sm:px-[34px] pt-[28px] pb-[48px]'
        }`}
      >
        <div
          key={currentPath}
          className={`w-full route-enter ${
            currentPath === '/agent'
              ? 'flex-1 flex flex-col min-h-0 h-full'
              : 'max-w-[1240px] mx-auto'
          }`}
        >
          {renderCurrentView()}
        </div>
      </main>

      {/* Global Modals */}
      <NewInvoiceModal
        isOpen={isNewInvoiceOpen}
        preselectedClientId={defaultNewInvoiceClientId}
        onClose={() => setIsNewInvoiceOpen(false)}
        onInvoiceCreated={(invoice) => {
          setFlashInvoiceId(invoice.invoice_id);
          setIsNewInvoiceOpen(false);
          triggerRefresh();
          addToast(`Created invoice ${invoice.invoice_number}`);
          setTimeout(() => setFlashInvoiceId(null), 800);
        }}
      />

      <RecordPaymentModal
        isOpen={!!recordPaymentInvoice}
        invoice={recordPaymentInvoice}
        onClose={() => setRecordPaymentInvoice(null)}
        onPaymentRecorded={({ payment, invoice }) => {
          setFlashPaymentId(payment.payment_id);
          setFlashInvoiceId(payment.invoice_id);
          setRecordPaymentInvoice(null);
          triggerRefresh();
          addToast(`Recorded ${payment.amount_display} — ${invoice.outstanding_display} left on ${invoice.invoice_number}`);
          setTimeout(() => {
            setFlashPaymentId(null);
            setFlashInvoiceId(null);
          }, 800);
        }}
      />

      <AddClientModal
        isOpen={isAddClientOpen}
        onClose={() => setIsAddClientOpen(false)}
        onClientAdded={(client) => {
          setIsAddClientOpen(false);
          triggerRefresh();
          addToast(`Added client ${client.name}`);
        }}
      />

      <DocumentViewerModal document={documentViewer} onClose={closeDocument} />
    </div>
    </DemoResetProvider>
  );
}

export default function App() {
  return (
    <ToastProvider>
      <MainApp />
    </ToastProvider>
  );
}

