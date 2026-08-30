from pathlib import Path


def test_forge_v3_migration_is_additive_secure_and_temporally_scoped() -> None:
    sql = (
        Path(__file__).resolve().parents[1] / "FORGE_V3_SUPABASE.sql"
    ).read_text(encoding="utf-8").lower()

    assert "create table if not exists public.forge_superstar_experiments" in sql
    assert "create table if not exists public.forge_superstar_state" in sql
    assert "create table if not exists public.forge_superstar_predictions" in sql
    assert "prospective_minimum >= 100" in sql
    assert "greatest(" in sql
    assert "superstar-legacy-v1" in sql
    assert "created_at < ((target_date + time '20:00')" in sql
    assert "distinct on" in sql
    assert "role = 'champion'" in sql
    assert "old.jolly" not in sql
    assert "old.n1" not in sql
    assert "if not superstar_changed then" in sql
    assert "where status = 'pending'" in sql
    assert "source_date >= new.data_estrazione" in sql
    assert "enable row level security" in sql
    assert "revoke all on table public.forge_superstar_predictions" in sql
    assert "revoke execute on function public.invalidate_forge_superstar_on_draw_change()" in sql
