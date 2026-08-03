import React from "react";
import { Link } from "react-router-dom";
import {
  Card,
  CardContent,
  CardHeader,
  CardTitle,
  CardDescription,
} from "@/components/ui/card";
import { useQuery } from "@tanstack/react-query";
import api from "../api/axios";
import {
  Users,
  AlertTriangle,
  DollarSign,
  TrendingUp,
  Briefcase,
  Loader2,
  CalendarDays,
} from "lucide-react";
import FilterBar from "../components/FilterBar";
import SalesChart from "../components/SalesChart";
import TopProducts from "../components/TopProducts";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";

const Dashboard = () => {
  const today = new Date().toISOString().split("T")[0];
  const role = localStorage.getItem("role");
  const formattedToday = new Intl.DateTimeFormat("uz-UZ", {
    weekday: "long",
    day: "numeric",
    month: "long",
  }).format(new Date());
  const [filters, setFilters] = React.useState({
    employee_id: "",
    start_date: today,
    end_date: today,
  });

  const {
    data: stats,
    isLoading,
    error,
  } = useQuery({
    queryKey: ["dashboard-stats", filters],
    queryFn: async () => {
      const params = {};
      if (filters.employee_id && filters.employee_id !== "all")
        params.employee_id = filters.employee_id;
      if (filters.start_date) params.start_date = filters.start_date;
      if (filters.end_date) params.end_date = filters.end_date;

      try {
        const response = await api.get("/finance/stats", { params });
        return response.data;
      } catch (e) {
        console.error("Stats API failed", e);
        throw e;
      }
    },
  });
  const { data: debtors = [] } = useQuery({
    queryKey: ["dashboard-debtors"],
    queryFn: async () => {
      const response = await api.get("/crm/clients/debts");
      return response.data;
    },
  });

  if (isLoading)
    return (
      <div className="flex flex-col items-center justify-center p-20 space-y-4">
        <Loader2 className="w-10 h-10 animate-spin text-primary" />
        <div className="text-center">
          <h3 className="text-lg font-medium">Baza bilan bog'lanilmoqda...</h3>
          <p className="text-sm text-muted-foreground">
            Server uyg'onishi 1-2 daqiqa vaqt olishi mumkin.
          </p>
        </div>
      </div>
    );
  if (error)
    return (
      <div className="p-8 text-destructive">
        Xatolik yuz berdi: {error.message}
      </div>
    );
  const overdueDebtors = debtors.filter(
    (client) => client.status === "overdue",
  );
  const totalDebt = debtors.reduce(
    (sum, client) => sum + (client.debt_amount || 0),
    0,
  );

  const cards = [
    {
      title: "Davr Savdosi",
      value: stats?.dailySalesFormatted || "0 so'm",
      icon: DollarSign,
      description: "Tanlangan vaqtdagi tushum",
      color: "text-blue-600 dark:text-blue-400",
      bg: "bg-blue-100/50 dark:bg-blue-900/20",
      iconBg: "bg-blue-100 dark:bg-blue-900/50",
      borderColor: "border-blue-200 dark:border-blue-800",
    },
    ...(role === "admin"
      ? [
          {
            title: "Sof Foyda",
            value: stats?.netProfitFormatted || "0 so'm",
            icon: TrendingUp,
            description: "Daromad - Chiqimlar",
            color: "text-emerald-600 dark:text-emerald-400",
            bg: "bg-emerald-100/50 dark:bg-emerald-900/20",
            iconBg: "bg-emerald-100 dark:bg-emerald-900/50",
            borderColor: "border-emerald-200 dark:border-emerald-800",
          },
        ]
      : []),
    ...(role === "admin" || role === "manager"
      ? [
          {
            title: "Xarajatlar",
            value: `${stats?.totalExpenses?.toLocaleString() || 0} so'm`,
            icon: Briefcase,
            description: "Jami chiqimlar",
            color: "text-amber-600 dark:text-amber-400",
            bg: "bg-amber-100/50 dark:bg-amber-900/20",
            iconBg: "bg-amber-100 dark:bg-amber-900/50",
            borderColor: "border-amber-200 dark:border-amber-800",
          },
        ]
      : []),
    {
      title: "Mijozlar",
      value: stats?.clientCount || "0",
      icon: Users,
      description: "Jami mijozlar",
      color: "text-indigo-600 dark:text-indigo-400",
      bg: "bg-indigo-100/50 dark:bg-indigo-900/20",
      iconBg: "bg-indigo-100 dark:bg-indigo-900/50",
      borderColor: "border-indigo-200 dark:border-indigo-800",
    },
  ];

  return (
    <div className="space-y-6">
      <section className="relative overflow-hidden rounded-2xl border bg-gradient-to-br from-primary/15 via-background to-background p-5 md:p-7">
        <div className="absolute -right-16 -top-20 h-56 w-56 rounded-full bg-primary/15 blur-3xl" />
        <div className="relative flex flex-col gap-5 lg:flex-row lg:items-end lg:justify-between">
          <div>
            <div className="mb-2 flex items-center gap-2 text-sm font-medium text-muted-foreground">
              <CalendarDays className="h-4 w-4" />
              <span className="capitalize">{formattedToday}</span>
            </div>
            <h2 className="text-3xl font-bold tracking-tight md:text-4xl">
              Boshqaruv paneli
            </h2>
            <p className="mt-2 max-w-xl text-muted-foreground">
              Savdo, zaxira va muhim holatlarni bir joyda kuzating.
            </p>
          </div>
        </div>
      </section>

      <section className="rounded-2xl border bg-card/70 p-3 shadow-sm backdrop-blur-sm">
        <FilterBar filters={filters} onFilterChange={setFilters} />
      </section>

      <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-4">
        {cards.map((card, index) => (
          <Card
            key={index}
            className={`group relative overflow-hidden border ${card.bg} ${card.borderColor} shadow-sm transition-all duration-300 hover:-translate-y-1 hover:shadow-lg`}
          >
            <div
              className={`absolute -right-6 -top-6 h-24 w-24 rounded-full ${card.iconBg} opacity-50 transition-transform duration-300 group-hover:scale-125`}
            />
            <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
              <CardTitle className="text-sm font-semibold text-muted-foreground">
                {card.title}
              </CardTitle>
              <div className={`p-2 rounded-full ${card.iconBg}`}>
                <card.icon className={`h-5 w-5 ${card.color}`} />
              </div>
            </CardHeader>
            <CardContent>
              <div className="text-3xl font-bold tracking-tight">
                {card.value}
              </div>
              <p className="text-xs text-muted-foreground mt-1 font-medium">
                {card.description}
              </p>
            </CardContent>
          </Card>
        ))}
      </div>

      {/* Low Stock Alert Section */}
      {stats?.lowStockItems?.length > 0 && (
        <Card className="border-amber-200 bg-amber-50/50 dark:bg-amber-900/10 dark:border-amber-900/50">
          <CardHeader className="pb-3">
            <div className="flex items-center justify-between">
              <div className="flex items-center gap-2">
                <div className="p-2 bg-amber-100 dark:bg-amber-900/50 rounded-lg">
                  <AlertTriangle className="h-5 w-5 text-amber-600" />
                </div>
                <div>
                  <CardTitle className="text-lg font-bold text-amber-900 dark:text-amber-100">
                    Kam qolgan mahsulotlar
                  </CardTitle>
                  <CardDescription className="text-amber-700/70 dark:text-amber-400/70">
                    Quyidagi mahsulotlar zaxirasi belgilangan limitdan kamayib
                    ketgan
                  </CardDescription>
                </div>
              </div>
              <Link to="/inventory">
                <Button
                  size="sm"
                  variant="outline"
                  className="h-8 border-amber-200 hover:bg-amber-100 text-amber-800"
                >
                  Hammasini ko'rish
                </Button>
              </Link>
            </div>
          </CardHeader>
          <CardContent>
            <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-3">
              {stats.lowStockItems.slice(0, 6).map((item) => (
                <div
                  key={item.id}
                  className="flex items-center justify-between p-3 rounded-xl bg-background/50 border border-amber-100 dark:border-amber-900/30"
                >
                  <div className="flex flex-col">
                    <span className="text-sm font-bold truncate max-w-[150px]">
                      {item.name}
                    </span>
                    <span className="text-[10px] text-muted-foreground uppercase font-medium">
                      {item.unit}
                    </span>
                  </div>
                  <Badge
                    variant="destructive"
                    className="bg-amber-100 text-amber-700 border-amber-200 hover:bg-amber-200 font-black px-2 py-0"
                  >
                    {item.stock} ta
                  </Badge>
                </div>
              ))}
            </div>
          </CardContent>
        </Card>
      )}

      {debtors.length > 0 && (
        <Card className="border-rose-200 bg-rose-50/50 dark:border-rose-900/50 dark:bg-rose-950/10">
          <CardContent className="flex flex-col gap-4 p-5 sm:flex-row sm:items-center sm:justify-between">
            <div className="flex items-start gap-3">
              <div className="rounded-xl bg-rose-100 p-2.5 text-rose-600 dark:bg-rose-900/40 dark:text-rose-300">
                <AlertTriangle className="h-5 w-5" />
              </div>
              <div>
                <p className="font-bold text-rose-950 dark:text-rose-100">
                  Qarzdorlik nazorati
                </p>
                <p className="mt-1 text-sm text-rose-800/80 dark:text-rose-300/80">
                  {overdueDebtors.length > 0
                    ? `${overdueDebtors.length} mijozning to‘lov muddati o‘tgan.`
                    : `${debtors.length} mijozda ochiq qarzdorlik bor.`}
                </p>
              </div>
            </div>
            <div className="flex items-center justify-between gap-4 sm:justify-end">
              <div className="text-right">
                <p className="text-xs font-medium text-rose-800/70 dark:text-rose-300/70">
                  Jami qarz
                </p>
                <p className="font-bold text-rose-950 dark:text-rose-100">
                  {totalDebt.toLocaleString()} so‘m
                </p>
              </div>
              <Link to="/crm">
                <Button
                  size="sm"
                  variant="outline"
                  className="border-rose-200 text-rose-700 hover:bg-rose-100 dark:border-rose-900 dark:text-rose-300 dark:hover:bg-rose-900/30"
                >
                  Ko‘rish
                </Button>
              </Link>
            </div>
          </CardContent>
        </Card>
      )}
      <div className="space-y-4">
        <SalesChart filters={filters} />
        <TopProducts filters={filters} />
      </div>
    </div>
  );
};

export default Dashboard;
