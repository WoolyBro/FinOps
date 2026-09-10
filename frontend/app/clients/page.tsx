"use client";

import { useCallback, useEffect, useState } from "react";
import Link from "next/link";
import { ApiError, api, type Client } from "@/lib/api";
import { Empty, LoadError, Loading, formatDate } from "@/components/common";
import { NewClientForm } from "@/components/forms";

export default function ClientsPage() {
  const [clients, setClients] = useState<Client[] | null>(null);
  const [error, setError] = useState<ApiError | null>(null);
  const [query, setQuery] = useState("");
  const [adding, setAdding] = useState(false);
  const [toast, setToast] = useState<string | null>(null);

  const load = useCallback(() => {
    api
      .clients()
      .then((body) => {
        setClients(body.clients);
        setError(null);
      })
      .catch((err) => setError(err as ApiError));
  }, []);

  useEffect(load, [load]);

  const shown = (clients ?? []).filter((client) =>
    `${client.name} ${client.email ?? ""}`
      .toLowerCase()
      .includes(query.trim().toLowerCase()),
  );

  return (
    <>
      <div className="page-head">
        <div>
          <h1 className="page-title">Clients</h1>
          <p className="page-sub">
            Names are deduplicated, so the same client cannot end up on the
            books twice under different spellings.
          </p>
        </div>
        <div className="actions">
          <button className="btn primary" onClick={() => setAdding(true)}>
            + New client
          </button>
        </div>
      </div>

      {error ? <LoadError error={error} /> : null}

      <div className="filter-bar">
        <input
          className="search"
          value={query}
          onChange={(e) => setQuery(e.target.value)}
          placeholder="Search clients"
          aria-label="Search clients"
        />
        <span className="range-caption">
          {clients ? `${shown.length} of ${clients.length}` : ""}
        </span>
      </div>

      <div className="panel">
        {clients === null && !error ? (
          <Loading what="clients" />
        ) : shown.length === 0 ? (
          <Empty>
            <strong>
              {clients?.length === 0 ? "No clients yet" : "No matches"}
            </strong>
            {clients?.length === 0
              ? "Add your first client, then raise an invoice against them."
              : "Try a different search."}
          </Empty>
        ) : (
          <div className="table-scroll">
            <table>
              <thead>
                <tr>
                  <th>Client</th>
                  <th>Email</th>
                  <th>Phone</th>
                  <th>Added</th>
                  <th className="num"></th>
                </tr>
              </thead>
              <tbody>
                {shown.map((client) => (
                  <tr key={client.client_id}>
                    <td>
                      <Link
                        className="link strong"
                        href={`/clients/${client.client_id}`}
                      >
                        {client.name}
                      </Link>
                    </td>
                    <td className="muted">{client.email ?? "—"}</td>
                    <td className="muted">{client.phone ?? "—"}</td>
                    <td className="muted">
                      {client.created_at
                        ? formatDate(client.created_at.slice(0, 10))
                        : "—"}
                    </td>
                    <td className="num">
                      <Link
                        className="btn"
                        href={`/clients/${client.client_id}`}
                      >
                        Open
                      </Link>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>

      {adding ? (
        <NewClientForm
          onClose={() => setAdding(false)}
          onDone={() => {
            load();
            setToast("Client added");
            setTimeout(() => setToast(null), 3000);
          }}
        />
      ) : null}

      {toast ? <div className="toast">{toast}</div> : null}
    </>
  );
}
