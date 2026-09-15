// Package netguard centralizes the SSRF host-allow policy so every place
// that dials a user-supplied target (API validation at creation time and the
// monitor worker at check time) enforces exactly the same rules.
package netguard

import (
	"context"
	"fmt"
	"net"
	"strings"
	"time"
)

// HostBlocked reports whether host must be rejected as a monitor target.
// It blocks loopback, link-local (incl. the 169.254.169.254 cloud metadata
// address), multicast and unspecified addresses unconditionally; "localhost"
// and RFC1918/ULA private-range addresses are blocked unless explicitly
// allowed via the matching flag. DNS lookups are bounded by a timeout so a
// user-controlled hostname cannot stall the caller.
func HostBlocked(host string, allowLocalhost, allowPrivate bool) bool {
	if strings.EqualFold(host, "localhost") {
		return !allowLocalhost
	}
	if ip := net.ParseIP(strings.Trim(host, "[]")); ip != nil {
		return ipBlocked(ip, allowPrivate)
	}
	ctx, cancel := context.WithTimeout(context.Background(), 3*time.Second)
	defer cancel()
	addrs, err := net.DefaultResolver.LookupHost(ctx, host)
	if err != nil {
		// Fail OPEN here by design: this is the creation-time/early UX check.
		// The fail-closed enforcement happens at dial time (ResolveAllowed
		// errors -> no connection is opened, and every dial re-validates the
		// freshly resolved IPs). Rejecting unresolvable names here would turn
		// transient DNS outages into undeletable-site UX bugs, while adding
		// no security once dials are pinned.
		return false
	}
	for _, addr := range addrs {
		if ip := net.ParseIP(addr); ip != nil && ipBlocked(ip, allowPrivate) {
			return true
		}
	}
	return false
}

// ResolveAllowed resolves host and returns only the IPs that pass the guard.
// Fail-closed like HostBlocked: DNS errors or zero allowed IPs yield an error.
// Callers must dial one of the returned IPs (pinning) instead of re-resolving
// the hostname at dial time — otherwise a second resolution can return a
// different (attacker-controlled) address (DNS-rebinding TOCTOU).
func ResolveAllowed(ctx context.Context, host string, allowLocalhost, allowPrivate bool) ([]net.IP, error) {
	if strings.EqualFold(host, "localhost") {
		if !allowLocalhost {
			return nil, fmt.Errorf("localhost not allowed")
		}
		return []net.IP{net.ParseIP("127.0.0.1")}, nil
	}
	if ip := net.ParseIP(strings.Trim(host, "[]")); ip != nil {
		if ipBlocked(ip, allowPrivate) {
			return nil, fmt.Errorf("IP not allowed: %s", host)
		}
		return []net.IP{ip}, nil
	}
	resCtx, cancel := context.WithTimeout(ctx, 3*time.Second)
	defer cancel()
	addrs, err := net.DefaultResolver.LookupHost(resCtx, host)
	if err != nil {
		return nil, fmt.Errorf("DNS lookup failed for %s", host)
	}
	var out []net.IP
	for _, addr := range addrs {
		if ip := net.ParseIP(addr); ip != nil && !ipBlocked(ip, allowPrivate) {
			out = append(out, ip)
		}
	}
	if len(out) == 0 {
		return nil, fmt.Errorf("no allowed addresses for %s", host)
	}
	return out, nil
}

func ipBlocked(ip net.IP, allowPrivate bool) bool {
	if ip.IsLoopback() || ip.IsLinkLocalUnicast() || ip.IsLinkLocalMulticast() || ip.IsMulticast() || ip.IsUnspecified() {
		return true
	}
	if !allowPrivate && ip.IsPrivate() {
		return true
	}
	return false
}
