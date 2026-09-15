package sim

import "testing"

func TestSimFlood(t *testing.T) {
	r := RunFlood(t, 60, 2)
	if r.Completed != 2 {
		t.Fatalf("cycles = %d, want 2", r.Completed)
	}
	if r.ActiveLeft != 0 {
		t.Fatalf("active left = %d, want 0 (slot leak)", r.ActiveLeft)
	}
	t.Logf("flood: %d sites x %d cycles in %dms", r.Sites, r.Cycles, r.ElapsedMs)
}

func TestSimChaos(t *testing.T) {
	r := RunChaos(t)
	if !r.CancelSafe || !r.CorruptKept || !r.QuotaBounded {
		t.Fatalf("chaos = %+v, want all true", r)
	}
}

func TestSimFailover(t *testing.T) {
	r := RunFailover(t)
	if r.Takeovers != 1 {
		t.Fatalf("takeovers = %d, want 1", r.Takeovers)
	}
	if r.Double {
		t.Fatalf("double-leader detected")
	}
	if r.Owner == "" {
		t.Fatalf("empty owner after takeover")
	}
}
