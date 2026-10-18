import { Link, useNavigate, useParams } from "react-router-dom";
import { Icon } from "../components/icons";
import ObjectTable from "../components/ObjectTable";
import ObjectView from "../components/ObjectView";
import { EmptyState, PageHeader, Panel, TypeIcon } from "../components/ui";
import { human } from "../ontologyText";
import { useOntology } from "../useOntology";

/** The object explorer: pick a type, browse or search its objects, open one into an Object View. */
export default function Objects() {
  const { label, id } = useParams();
  const nav = useNavigate();
  const { view, spec, style, loading } = useOntology();
  const counts = view?.counts.nodes ?? {};

  if (!spec) return <div className="p-6 text-[12px] text-faint">{loading ? "Loading…" : "No ontology yet."}</div>;
  if (!view?.has_approved) {
    return (
      <div className="p-6">
        <EmptyState icon="table" title="No data loaded yet" action={<Link to="/ontology" className="link text-[12px]">Review the ontology</Link>}>
          Objects appear here once the ontology is approved and the data is loaded.
        </EmptyState>
      </div>
    );
  }

  const type = spec.types.find((t) => t.label === label) ?? null;
  const total = Object.values(counts).reduce((a, b) => a + b, 0);

  return (
    <div className="flex h-full min-h-[600px] flex-col">
      <PageHeader
        crumbs={[{ label: "Object explorer", to: "/objects" }, ...(type ? [{ label: human(type.label), to: id ? `/objects/${encodeURIComponent(type.label)}` : undefined }] : []), ...(id ? [{ label: id }] : [])]}
        icon={<span className="flex h-9 w-9 items-center justify-center rounded-[4px] bg-accent-soft text-accent"><Icon name="table" size={20} /></span>}
        title={type ? `${human(type.label)} objects` : "Object explorer"}
        subtitle={type ? type.description : `${total.toLocaleString()} objects across ${spec.types.length} object types. Pick a type, or press / to search everything.`}
      />
      <div className="grid min-h-0 flex-1 gap-3 p-3 lg:grid-cols-[240px_minmax(0,1fr)]">
        <Panel title="Object types" icon="cube" count={spec.types.length} className="hidden lg:flex">
          <div className="p-1.5">
            {spec.types.map((t) => {
              const s = style(t.label);
              const active = t.label === label;
              return (
                <button key={t.label} onClick={() => nav(`/objects/${encodeURIComponent(t.label)}`)}
                        className={`flex w-full items-center gap-2 rounded-[3px] px-2 py-1.5 text-left hover:bg-hover ${active ? "bg-accent-soft shadow-[inset_2px_0_0] shadow-accent" : ""}`}>
                  <TypeIcon label={t.label} color={s.color} icon={s.icon} size={22} />
                  <span className="min-w-0 flex-1 truncate text-[12.5px] font-medium text-ink">{human(t.label)}</span>
                  <span className="text-[11px] tabular-nums text-muted">{(counts[t.label] ?? 0).toLocaleString()}</span>
                </button>
              );
            })}
          </div>
        </Panel>

        {!type ? (
          <div className="grid content-start gap-3 sm:grid-cols-2 xl:grid-cols-3">
            {spec.types.map((t) => {
              const s = style(t.label);
              return (
                <button key={t.label} onClick={() => nav(`/objects/${encodeURIComponent(t.label)}`)}
                        className="group flex flex-col gap-2 rounded-[4px] border border-line bg-panel p-3 text-left transition-colors hover:border-line-strong hover:bg-raised">
                  <div className="flex items-center gap-2.5">
                    <TypeIcon label={t.label} color={s.color} icon={s.icon} size={30} />
                    <div className="min-w-0 flex-1">
                      <div className="truncate text-[13.5px] font-semibold text-ink">{human(t.label)}</div>
                      <div className="text-[11px] text-faint">{t.properties.length} properties</div>
                    </div>
                    <div className="text-right">
                      <div className="text-[18px] font-semibold tabular-nums text-ink">{(counts[t.label] ?? 0).toLocaleString()}</div>
                      <div className="text-[10px] uppercase tracking-wide text-faint">objects</div>
                    </div>
                  </div>
                  <p className="line-clamp-2 text-[12px] text-muted">{t.description}</p>
                </button>
              );
            })}
          </div>
        ) : (
          <div className={`grid min-h-0 gap-3 ${id ? "xl:grid-cols-[minmax(0,1fr)_minmax(420px,44%)]" : ""}`}>
            <section className={`min-h-[420px] overflow-hidden rounded-[4px] border border-line bg-panel ${id ? "hidden xl:block" : ""}`}>
              <ObjectTable type={type} className="h-full" selectedId={id} maxColumns={id ? 3 : 6}
                           onOpen={(oid) => nav(`/objects/${encodeURIComponent(type.label)}/${encodeURIComponent(oid)}`)} />
            </section>
            {id && (
              <section className="min-h-[520px] overflow-hidden rounded-[4px] border border-line">
                <ObjectView key={`${type.label}/${id}`} label={type.label} id={id}
                            onClose={() => nav(`/objects/${encodeURIComponent(type.label)}`)} />
              </section>
            )}
          </div>
        )}
      </div>
    </div>
  );
}
