import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useState } from "react";
import { Link, useParams } from "react-router";
import { api, download, errorMessage, unwrap } from "../../api/client";
import { StatusBadge } from "../../components/domain";
import { Button, Card, ErrorBox, KeyValue, Spinner } from "../../components/ui";
import { formatPkr, humanize } from "../../lib/format";

export function VendorOrderPage() {
  const { orderId = "" } = useParams();
  const queryClient = useQueryClient();
  const path = { params: { path: { order_id: orderId } } };
  const order = useQuery({
    queryKey: ["vendor", "order", orderId],
    queryFn: () => unwrap(api.GET("/api/v1/vendor/orders/{order_id}", path)),
  });
  const [error, setError] = useState<string | null>(null);
  const advance = useMutation({
    mutationFn: (step: "start-printing" | "ready-for-dispatch") =>
      step === "start-printing"
        ? unwrap(api.POST("/api/v1/vendor/orders/{order_id}/start-printing", path))
        : unwrap(api.POST("/api/v1/vendor/orders/{order_id}/ready-for-dispatch", path)),
    onSuccess: (updated) => {
      queryClient.setQueryData(["vendor", "order", orderId], updated);
      void queryClient.invalidateQueries({ queryKey: ["vendor", "orders"] });
    },
  });

  const openPdf = async () => {
    setError(null);
    try {
      const file = await unwrap(api.GET("/api/v1/vendor/orders/{order_id}/file-url", path));
      window.location.assign(file.url);
    } catch (err) {
      setError(errorMessage(err));
    }
  };

  if (order.isPending) return <Spinner />;
  if (order.isError) return <ErrorBox message={errorMessage(order.error)} />;
  const o = order.data;
  return (
    <div className="max-w-3xl space-y-4">
      <div className="flex flex-wrap items-center gap-3">
        <Link to="/vendor" className="text-sm text-brand-800 hover:underline">
          ← Print queue
        </Link>
        <h1 className="font-mono text-xl font-semibold">{o.code}</h1>
        <StatusBadge status={o.status} />
      </div>
      {(error || advance.isError) && <ErrorBox message={error ?? errorMessage(advance.error)} />}
      <Card title="What to make">
        <KeyValue
          items={[
            ["Item", o.title],
            ["Pages", o.pages],
            ["Paper", o.paper && humanize(o.paper)],
            ["Binding", o.binding && humanize(o.binding)],
            ["Copies", o.copies],
          ]}
        />
      </Card>
      <Card title="Deliver to">
        <KeyValue
          items={[
            ["Recipient", o.shipping.recipient_name],
            ["Phone", o.shipping.recipient_phone_e164],
            [
              "Address",
              `${o.shipping.street_address}, ${o.shipping.area}, ${o.shipping.city_name}`,
            ],
            ["Landmark", o.shipping.landmark],
            [
              "COD to collect",
              o.cod_amount_paisa ? <strong>{formatPkr(o.cod_amount_paisa)}</strong> : "Paid online",
            ],
            ["CN", o.cn_number],
          ]}
        />
      </Card>
      <div className="flex flex-wrap gap-2">
        {o.file_available && (
          <Button variant="secondary" onClick={() => void openPdf()}>
            Download PDF
          </Button>
        )}
        <Button
          variant="secondary"
          onClick={() =>
            download(
              `/api/v1/vendor/orders/${o.id}/packing-slip`,
              `packing-slip-${o.code}.pdf`,
            ).catch((e) => setError(errorMessage(e)))
          }
        >
          Packing slip
        </Button>
        {o.allowed_actions.includes("start-printing") && (
          <Button busy={advance.isPending} onClick={() => advance.mutate("start-printing")}>
            Start printing
          </Button>
        )}
        {o.allowed_actions.includes("ready-for-dispatch") && (
          <Button busy={advance.isPending} onClick={() => advance.mutate("ready-for-dispatch")}>
            Ready for dispatch
          </Button>
        )}
      </div>
    </div>
  );
}
