// Package netguard centralizes the SSRF host-allow policy so every place
// that dials a user-supplied target (API validation at creation time and the
// monitor worker at check time) enforces exactly the same rules.
package netguard

import (
	"context"
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
		// Unresolvable now; the caller's own dial will fail on its own. Treating
		// this as "not blocked" avoids turning transient DNS errors into a
		// guard bypass discussion - the actual connection attempt still can't
		// reach anything if the name doesn't resolve.
		return false
	}
	for _, addr := range addrs {
		if ip := net.ParseIP(addr); ip != nil && ipBlocked(ip, allowPrivate) {
			return true
		}
	}
	return false
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
