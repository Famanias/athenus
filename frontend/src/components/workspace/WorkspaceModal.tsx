import React, { useState } from 'react';
import { useAppStore } from '@/store/useAppStore';
import { createWorkspace, updateWorkspace, deleteWorkspace } from '@/services/libraryService';
import { Button } from '@/components/ui/Button';

const WORKSPACE_ICONS = [
  'psychology', 'school', 'science', 'terminal', 'code',
  'auto_stories', 'analytics', 'architecture', 'biotech', 'equalizer'
];

export const WorkspaceModal: React.FC = () => {
  const {
    isWorkspaceModalOpen,
    setWorkspaceModalOpen,
    workspaces,
    setWorkspaces,
    activeWorkspaceId,
    switchWorkspace,
  } = useAppStore();

  const [name, setName] = useState('');
  const [description, setDescription] = useState('');
  const [selectedIcon, setSelectedIcon] = useState('psychology');
  const [editingWorkspaceId, setEditingWorkspaceId] = useState<string | null>(null);
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [deletingWorkspaceId, setDeletingWorkspaceId] = useState<string | null>(null);

  if (!isWorkspaceModalOpen) return null;

  const handleClose = () => {
    setName('');
    setDescription('');
    setSelectedIcon('psychology');
    setEditingWorkspaceId(null);
    setWorkspaceModalOpen(false);
  };

  const handleCreateOrUpdate = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!name.trim() || isSubmitting) return;

    setIsSubmitting(true);
    try {
      if (editingWorkspaceId) {
        const updated = await updateWorkspace(editingWorkspaceId, {
          name: name.trim(),
          description: description.trim() || undefined,
          icon: selectedIcon,
        });
        setWorkspaces(workspaces.map((w) => (w.id === updated.id ? updated : w)));
      } else {
        const created = await createWorkspace({
          name: name.trim(),
          description: description.trim() || undefined,
          icon: selectedIcon,
        });
        setWorkspaces([created, ...workspaces]);
        switchWorkspace(created.id);
      }
      handleClose();
    } catch {
      // Handle error gracefully
    } finally {
      setIsSubmitting(false);
    }
  };

  const handleConfirmDelete = async (workspaceId: string) => {
    try {
      const res = await deleteWorkspace(workspaceId);
      setWorkspaces(workspaces.filter((w) => w.id !== workspaceId));
      if (workspaceId === activeWorkspaceId && res.active_workspace_id) {
        switchWorkspace(res.active_workspace_id);
      }
    } catch {
      // Handle delete error
    } finally {
      setDeletingWorkspaceId(null);
    }
  };

  const startEditing = (wsId: string) => {
    const ws = workspaces.find((w) => w.id === wsId);
    if (ws) {
      setEditingWorkspaceId(ws.id);
      setName(ws.name);
      setDescription(ws.description || '');
      setSelectedIcon(ws.icon || 'psychology');
    }
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 backdrop-blur-sm p-4">
      <div
        className="bg-surface-container-high border border-outline-variant rounded-xl w-full max-w-lg shadow-2xl flex flex-col max-h-[85vh] overflow-hidden"
        onClick={(e) => e.stopPropagation()}
      >
        {/* Header */}
        <div className="px-6 py-4 border-b border-outline-variant flex justify-between items-center bg-surface-container-low">
          <div className="flex items-center gap-2">
            <span className="material-symbols-outlined text-secondary">
              {editingWorkspaceId ? 'edit' : 'add_box'}
            </span>
            <h2 className="font-bold text-base text-on-surface font-type-light">
              {editingWorkspaceId ? 'Manage Learning Workspace' : 'Create New Learning Workspace'}
            </h2>
          </div>
          <button
            onClick={handleClose}
            className="text-on-surface-variant hover:text-on-surface p-1 rounded hover:bg-surface-container transition-colors"
          >
            <span className="material-symbols-outlined text-sm">close</span>
          </button>
        </div>

        {/* Form Body */}
        <form onSubmit={handleCreateOrUpdate} className="p-6 space-y-4 overflow-y-auto custom-scrollbar">
          <div>
            <label className="block text-xs font-mono text-secondary mb-1">WORKSPACE NAME *</label>
            <input
              type="text"
              required
              value={name}
              onChange={(e) => setName(e.target.value)}
              placeholder="e.g., Computer Vision & Image Processing"
              className="w-full bg-surface-container-low border border-outline-variant rounded px-3 py-2 text-xs text-on-surface focus:outline-none focus:border-secondary"
            />
          </div>

          <div>
            <label className="block text-xs font-mono text-secondary mb-1">DESCRIPTION (OPTIONAL)</label>
            <textarea
              rows={2}
              value={description}
              onChange={(e) => setDescription(e.target.value)}
              placeholder="e.g., Lectures on CNNs, Object Detection, and Segmentation."
              className="w-full bg-surface-container-low border border-outline-variant rounded px-3 py-2 text-xs text-on-surface focus:outline-none focus:border-secondary resize-none"
            />
          </div>

          <div>
            <label className="block text-xs font-mono text-secondary mb-2">ICON BADGE</label>
            <div className="flex flex-wrap gap-2">
              {WORKSPACE_ICONS.map((icon) => (
                <button
                  key={icon}
                  type="button"
                  onClick={() => setSelectedIcon(icon)}
                  className={`w-9 h-9 rounded flex items-center justify-center border transition-all ${
                    selectedIcon === icon
                      ? 'border-secondary bg-secondary/10 text-secondary'
                      : 'border-outline-variant bg-surface-container-low text-on-surface-variant hover:border-outline-variant/80'
                  }`}
                >
                  <span className="material-symbols-outlined text-sm">{icon}</span>
                </button>
              ))}
            </div>
          </div>

          <div className="pt-2 flex justify-end gap-2">
            {editingWorkspaceId && (
              <Button
                type="button"
                variant="secondary"
                size="sm"
                onClick={() => {
                  setEditingWorkspaceId(null);
                  setName('');
                  setDescription('');
                }}
              >
                Cancel Edit
              </Button>
            )}
            <Button type="submit" variant="primary" size="sm" disabled={isSubmitting}>
              {isSubmitting ? 'Saving...' : editingWorkspaceId ? 'Update Workspace' : 'Create Workspace'}
            </Button>
          </div>
        </form>

        {/* Existing Workspaces List */}
        {workspaces.length > 0 && (
          <div className="border-t border-outline-variant p-4 bg-surface-container-low/50">
            <h3 className="text-[11px] font-mono text-secondary font-semibold uppercase mb-2">
              Existing Workspaces ({workspaces.length})
            </h3>
            <div className="space-y-1 max-h-36 overflow-y-auto custom-scrollbar">
              {workspaces.map((ws) => {
                if (deletingWorkspaceId === ws.id) {
                  return (
                    <div
                      key={ws.id}
                      className="flex items-center justify-between p-2 rounded text-xs border border-error/50 bg-error/10 text-on-surface"
                    >
                      <span className="text-xs font-semibold text-error truncate max-w-[200px]">
                        Delete &quot;{ws.name}&quot;?
                      </span>
                      <div className="flex items-center gap-1 shrink-0">
                        <button
                          type="button"
                          onClick={() => handleConfirmDelete(ws.id)}
                          className="px-2 py-0.5 bg-error text-on-error font-bold text-[11px] rounded hover:bg-error/80 transition-colors"
                        >
                          Confirm
                        </button>
                        <button
                          type="button"
                          onClick={() => setDeletingWorkspaceId(null)}
                          className="px-2 py-0.5 bg-surface-container text-on-surface-variant font-medium text-[11px] rounded hover:bg-surface-container-high transition-colors"
                        >
                          Cancel
                        </button>
                      </div>
                    </div>
                  );
                }

                return (
                  <div
                    key={ws.id}
                    className={`flex items-center justify-between p-2 rounded text-xs border transition-colors ${
                      ws.id === activeWorkspaceId
                        ? 'bg-surface-container border-secondary/40 text-on-surface'
                        : 'border-transparent text-on-surface-variant hover:bg-surface-container'
                    }`}
                  >
                    <div className="flex items-center gap-2 truncate pr-2">
                      <span className="material-symbols-outlined text-xs text-secondary shrink-0">
                        {ws.icon || 'psychology'}
                      </span>
                      <span className="truncate font-medium">{ws.name}</span>
                      {ws.id === activeWorkspaceId && (
                        <span className="bg-secondary/20 text-secondary text-[9px] px-1.5 py-0.5 rounded font-mono shrink-0">
                          ACTIVE
                        </span>
                      )}
                    </div>
                    <div className="flex items-center gap-1 shrink-0">
                      <button
                        type="button"
                        onClick={() => startEditing(ws.id)}
                        className="p-1 hover:text-on-surface text-on-surface-variant rounded hover:bg-surface-container-high"
                        title="Edit workspace"
                      >
                        <span className="material-symbols-outlined text-xs">edit</span>
                      </button>
                      {workspaces.length > 1 && (
                        <button
                          type="button"
                          onClick={() => setDeletingWorkspaceId(ws.id)}
                          className="p-1 hover:text-error text-on-surface-variant rounded hover:bg-surface-container-high"
                          title="Delete workspace"
                        >
                          <span className="material-symbols-outlined text-xs">delete</span>
                        </button>
                      )}
                    </div>
                  </div>
                );
              })}
            </div>
          </div>
        )}
      </div>
    </div>
  );
};
