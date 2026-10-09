import type { Schemas } from "../../api/client";
import { Button, Dialog } from "../../components/ui";

/** Shows a new login's temporary password (and TOTP link for admins) once. */
export function StaffCreatedDialog({
  created,
  onClose,
}: {
  created: Schemas["StaffUserCreated"] | null;
  onClose: () => void;
}) {
  return (
    <Dialog title="Login created" open={created !== null} onClose={onClose}>
      {created && (
        <div className="space-y-3 text-sm">
          <p>
            Share these details with <strong>{created.user.email}</strong> over a secure channel.
            They are shown only once.
          </p>
          <p>
            Temporary password:{" "}
            <code className="rounded bg-slate-100 px-2 py-1 font-mono">
              {created.temporary_password}
            </code>
          </p>
          {created.totp_provisioning_uri && (
            <p className="break-all">
              Authenticator setup link (add to Google Authenticator or similar):{" "}
              <code className="rounded bg-slate-100 px-1 font-mono text-xs">
                {created.totp_provisioning_uri}
              </code>
            </p>
          )}
          <Button onClick={onClose}>Done</Button>
        </div>
      )}
    </Dialog>
  );
}
