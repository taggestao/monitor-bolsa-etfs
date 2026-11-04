"""
periods.py — retornos da carteira TAG em qualquer fechamento mensal.

Usa os retornos mensais do Morningstar (HP010 Monthly Return; CSPX = variação mensal do Daily
Return Index HS793) guardados em morningstar_data.json. Para cada fim de mês M calcula, por ETF e
para a carteira: retorno no mês, 3M, YTD, 12M, 24M e 36M anualizados, vol 12M (desvio-padrão dos
12 retornos mensais × √12, como o "Std Dev 1 Yr (Mo-End)" do Morningstar), retorno desde a entrada
de cada tema e retorno por ano-calendário. build_tag_equities.py grava o resultado em
tag_equities.json ("periods"), e o app mostra o fechamento escolhido pelo usuário.
"""
import calendar
import datetime as dt
import math


def month_end(y, m):
    return dt.date(y, m, calendar.monthrange(y, m)[1])


def add_months(d, n):
    y, m = divmod(d.year * 12 + d.month - 1 + n, 12)
    return month_end(y, m + 1)


class MonthlySeries:
    """Retornos mensais (%) de um ETF, indexados pelo fim do mês."""

    def __init__(self, returns, anchor_date=None, anchor_idx=None):
        self.r = {dt.date.fromisoformat(k): v for k, v in returns.items()}
        self.anchor_date = dt.date.fromisoformat(anchor_date) if anchor_date else None
        self.anchor_idx = anchor_idx

    def cum(self, start, end):
        """Retorno acumulado (fração) do fim de `start` ao fim de `end`; None se faltar algum mês."""
        if end <= start:
            return 0.0 if end == start else None
        acc, d = 1.0, add_months(start, 1)
        while d <= end:
            if d not in self.r:
                return None
            acc *= 1 + self.r[d] / 100
            d = add_months(d, 1)
        return acc - 1

    def index(self, d):
        """Daily Return Index (HS793) no fim do mês d, encadeado a partir da âncora."""
        if self.anchor_date is None:
            return None
        if d >= self.anchor_date:
            c = self.cum(self.anchor_date, d)
            return None if c is None else self.anchor_idx * (1 + c)
        c = self.cum(d, self.anchor_date)
        return None if c is None else self.anchor_idx / (1 + c)

    def vol(self, end, n=12):
        rets = [self.r.get(add_months(end, -i)) for i in range(n)]
        if any(v is None for v in rets):
            return None
        mean = sum(rets) / n
        return math.sqrt(sum((v - mean) ** 2 for v in rets) / (n - 1)) * math.sqrt(12)


def _pct(x):
    return None if x is None else x * 100


def _ann(c, years):
    return None if c is None else ((1 + c) ** (1 / years) - 1) * 100


def etf_period(s, m):
    return {
        "mtd": s.r.get(m),
        "r3m": _pct(s.cum(add_months(m, -3), m)),
        "ytd": _pct(s.cum(month_end(m.year - 1, 12), m)),
        "r1y": _pct(s.cum(add_months(m, -12), m)),
        "r2y": _ann(s.cum(add_months(m, -24), m), 2),
        "r3y": _ann(s.cum(add_months(m, -36), m), 3),
        "vol1y": s.vol(m),
    }


def daily_stats(index_by_date, end):
    """Retorno e vol anualizada (dias úteis negociados) de uma série diária até `end`."""
    days = sorted(d for d in index_by_date if d <= end.isoformat())
    if len(days) < 3:
        return None, None, 0
    idx = [index_by_date[d] for d in days]
    traded = [idx[0]] + [b for a, b in zip(idx, idx[1:]) if b != a]
    rets = [b / a - 1 for a, b in zip(traded, traded[1:])]
    mean = sum(rets) / len(rets)
    sd = math.sqrt(sum((r - mean) ** 2 for r in rets) / (len(rets) - 1))
    return (idx[-1] / idx[0] - 1) * 100, sd * math.sqrt(252) * 100, len(rets)


def weighted(pairs):
    pairs = [(w, x) for w, x in pairs if x is not None]
    tw = sum(w for w, _ in pairs)
    return (sum(w * x for w, x in pairs) / tw, tw) if pairs else (None, 0)
