import React from "react";

export default function CampaignsAlert({ alert }) {
  if (!alert) return null;

  const alertClass =
    alert.type === "success"
      ? "alert alert-success"
      : alert.type === "error"
        ? "alert alert-error"
        : "alert alert-info";

  return (
    <div className="toast toast-top toast-center" aria-live="polite">
      <div role="alert" className={alertClass}>
        <svg xmlns="http://www.w3.org/2000/svg" className="alert-icon" fill="none" viewBox="0 0 24 24">
          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M9 12l2 2 4-4m6 2a9 9 0 11-18 0 9 9 0 0118 0z" />
        </svg>
        <span>{alert.message}</span>
      </div>
    </div>
  );
}
