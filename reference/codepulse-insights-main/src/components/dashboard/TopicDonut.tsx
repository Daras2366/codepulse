import { Cell, Pie, PieChart, ResponsiveContainer, Tooltip } from "recharts";

import { Panel } from "@/components/ui-kit/Panel";
import { topics } from "@/lib/mock-data";

export function TopicDonut() {
  const total = topics.reduce((s, t) => s + t.value, 0);

  return (
    <Panel title="Topic breakdown" caption="Where your solved problems come from">
      <div className="flex flex-col items-center gap-6 sm:flex-row sm:gap-8">
        <div className="relative h-[220px] w-[220px] shrink-0">
          <ResponsiveContainer width="100%" height="100%">
            <PieChart>
              <Pie
                data={topics}
                dataKey="value"
                innerRadius={68}
                outerRadius={100}
                paddingAngle={3}
                cornerRadius={8}
                stroke="none"
                animationDuration={900}
              >
                {topics.map((t) => (
                  <Cell key={t.name} fill={t.color} />
                ))}
              </Pie>
              <Tooltip
                content={({ active, payload }: any) =>
                  active && payload?.length ? (
                    <div className="surface-card px-3.5 py-2">
                      <p className="text-caption font-semibold">{payload[0].name}</p>
                      <p className="text-label text-muted-foreground">
                        {payload[0].value} solved · {Math.round((payload[0].value / total) * 100)}%
                      </p>
                    </div>
                  ) : null
                }
              />
            </PieChart>
          </ResponsiveContainer>
          <div className="pointer-events-none absolute inset-0 flex flex-col items-center justify-center">
            <span className="text-h2">{total}</span>
            <span className="text-label text-subtle">tagged</span>
          </div>
        </div>

        <ul className="w-full space-y-2.5">
          {topics.map((t) => (
            <li key={t.name} className="flex items-center gap-3">
              <span className="h-2.5 w-2.5 shrink-0 rounded-full" style={{ background: t.color }} />
              <span className="text-caption text-muted-foreground">{t.name}</span>
              <span className="text-caption ml-auto font-semibold">{t.value}</span>
            </li>
          ))}
        </ul>
      </div>
    </Panel>
  );
}
