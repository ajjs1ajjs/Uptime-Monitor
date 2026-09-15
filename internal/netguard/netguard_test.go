package netguard

import (
	"context"
	"testing"
	"time"
)

func TestHostBlockedLiterals(t *testing.T) {
	for _, h := range []string{"127.0.0.1", "::1", "0.0.0.0", "169.254.169.254", "224.0.0.1", "localhost"} {
		if !HostBlocked(h, false, false) {
			t.Fatalf("HostBlocked(%q) = false, want true", h)
		}
	}
	if HostBlocked("8.8.8.8", false, false) {
		t.Fatalf("HostBlocked(8.8.8.8) = true, want false")
	}
	if HostBlocked("10.0.0.1", false, true) {
		t.Fatalf("HostBlocked(10.0.0.1 allowPrivate) = true, want false")
	}
	if !HostBlocked("10.0.0.1", false, false) {
		t.Fatalf("HostBlocked(10.0.0.1) = false, want true")
	}
}

func TestResolveAllowedPinsIPs(t *testing.T) {
	ctx, cancel := context.WithTimeout(context.Background(), 5*time.Second)
	defer cancel()
	if _, err := ResolveAllowed(ctx, "169.254.169.254", false, false); err == nil {
		t.Fatalf("ResolveAllowed(metadata) = nil error, want blocked")
	}
	if _, err := ResolveAllowed(ctx, "127.0.0.1", false, false); err == nil {
		t.Fatalf("ResolveAllowed(loopback) = nil error, want blocked")
	}
	ips, err := ResolveAllowed(ctx, "8.8.8.8", false, false)
	if err != nil || len(ips) != 1 || ips[0].String() != "8.8.8.8" {
		t.Fatalf("ResolveAllowed(8.8.8.8) = %v, %v; want [8.8.8.8], nil", ips, err)
	}
}
