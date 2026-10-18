// Subtle backend/model state indicator for the header.
export default function ModelStatus({ state, info }) {
  const labels = {
    checking: "Checking backend",
    ok: "Model loaded",
    online: "Backend online",
    not_loaded: "Model not loaded",
    down: "Backend unreachable",
    demo: "Demo mode - no backend call",
  };
  const model = info?.model;
  const title =
    state === "ok" && model
      ? [
          model.test_auc != null && `Held-out AUC ${Number(model.test_auc).toFixed(2)}`,
          model.train_images != null && `trained on ${model.train_images} images`,
        ]
          .filter(Boolean)
          .join(", ") || undefined
      : undefined;
  return (
    <p className={`status status--${state}`} role="status" title={title}>
      <span className="status__dot" aria-hidden="true" />
      {labels[state] ?? labels.checking}
    </p>
  );
}
