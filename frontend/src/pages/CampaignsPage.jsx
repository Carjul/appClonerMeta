import React from "react";
import CampaignsAlert from "../components/campaigns/CampaignsAlert";
import CampaignsHeader from "../components/campaigns/CampaignsHeader";
import AccountCampaignsBlock from "../components/campaigns/AccountCampaignsBlock";
import CampaignActionsPanel from "../components/campaigns/CampaignActionsPanel";
import JobsPanel from "../components/campaigns/JobsPanel";
import useCampaignsController from "../hooks/useCampaignsController";

export default function CampaignsPage() {
  const {
    alert,
    configs,
    configId,
    accountFilter,
    accounts,
    filteredAccounts,
    expandAllAccounts,
    selectedCampaigns,
    selectedAccountId,
    selectedIds,
    bulkCampaignId,
    targetStatus,
    jobs,
    selectedJobs,
    allJobsSelected,
    selectedJobId,
    jobLogs,
    setConfigId,
    setExpandAllAccounts,
    setBulkCampaignId,
    setTargetStatus,
    onChangeAccountFilter,
    toggleCampaign,
    toggleAccountCampaigns,
    toggleJobSelection,
    toggleAllJobs,
    runExplorer,
    runBulk,
    runSingle,
    runDeleteCampaigns,
    runCampaignStatus,
    removeSelectedJobs,
    openLogs,
    cancel,
    copyCampaignId,
  } = useCampaignsController();

  return (
    <div className="panel-grid single-col">
      <CampaignsAlert alert={alert} />
      <section className="panel">
        <CampaignsHeader
          accountFilter={accountFilter}
          accounts={accounts}
          onChangeAccountFilter={onChangeAccountFilter}
          expandAllAccounts={expandAllAccounts}
          onToggleExpandAll={setExpandAllAccounts}
          configId={configId}
          configs={configs}
          onChangeConfig={setConfigId}
          onRunExplorer={runExplorer}
        />

        {filteredAccounts.map((acc) => (
          <AccountCampaignsBlock
            key={acc.account_id}
            account={acc}
            expandAllAccounts={expandAllAccounts}
            selectedCampaigns={selectedCampaigns}
            selectedAccountId={selectedAccountId}
            onToggleAccountCampaigns={toggleAccountCampaigns}
            onToggleCampaign={toggleCampaign}
            onCopyCampaignId={copyCampaignId}
          />
        ))}
      </section>

      <CampaignActionsPanel
        selectedCount={selectedIds.length}
        bulkCampaignId={bulkCampaignId}
        onChangeBulkCampaignId={setBulkCampaignId}
        onRunBulk={runBulk}
        onRunSingle={runSingle}
        targetStatus={targetStatus}
        onChangeTargetStatus={setTargetStatus}
        onRunStatus={runCampaignStatus}
        onRunDelete={runDeleteCampaigns}
      />

      <JobsPanel
        jobs={jobs}
        selectedJobs={selectedJobs}
        allJobsSelected={allJobsSelected}
        onToggleAllJobs={toggleAllJobs}
        onToggleJobSelection={toggleJobSelection}
        onRemoveSelectedJobs={removeSelectedJobs}
        onOpenLogs={openLogs}
        onCancelJob={cancel}
        selectedJobId={selectedJobId}
        jobLogs={jobLogs}
      />
    </div>
  );
}
