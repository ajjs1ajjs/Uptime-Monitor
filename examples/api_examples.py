#!/usr/bin/env python3
"""
Uptime Monitor API Examples

This script demonstrates how to use the Uptime Monitor API for:
- Authentication
- Site management
- Status checking
- SSL monitoring
- Notifications

Requirements:
    pip install requests

Usage:
    python examples/api_examples.py
"""

import json
from datetime import datetime

import requests

# Configuration
BASE_URL = "http://localhost:8080"
USERNAME = "admin"
PASSWORD = "admin"


class UptimeMonitorClient:
    """Uptime Monitor API Client"""

    def __init__(self, base_url=BASE_URL):
        self.base_url = base_url
        self.session = requests.Session()

    def login(self, username=USERNAME, password=PASSWORD):
        """Authenticate and get session cookie"""
        print(f"🔐 Logging in as {username}...")

        response = self.session.post(
            f"{self.base_url}/login",
            data={"username": username, "password": password},
            allow_redirects=False,
        )

        if response.status_code in [200, 302]:
            print(f"✅ Login successful!")
            return True
        else:
            print(f"❌ Login failed: {response.status_code}")
            return False

    # ========================================================================
    # Site Management
    # ========================================================================

    def list_sites(self):
        """Get list of all monitored sites"""
        print("\n📋 Listing all sites...")

        response = self.session.get(f"{self.base_url}/api/sites")

        if response.status_code == 200:
            sites = response.json().get("sites", [])
            print(f"✅ Found {len(sites)} sites:")
            for site in sites:
                status_icon = "🟢" if site.get("status") == "up" else "🔴"
                uptime = site.get("uptime", 0)
                print(f"   {status_icon} {site['name']} ({site['url']}) - Uptime: {uptime}%")
            return sites
        else:
            print(f"❌ Failed: {response.status_code}")
            return []

    def add_site(self, name, url, check_interval=60, notify_methods=None):
        """Add a new site to monitor"""
        print(f"\n➕ Adding site: {name}...")

        response = self.session.post(
            f"{self.base_url}/api/sites",
            json={
                "name": name,
                "url": url,
                "check_interval": check_interval,
                "is_active": True,
                "notify_methods": notify_methods or [],
                "monitor_type": "http",
            },
        )

        if response.status_code == 200:
            data = response.json()
            print(f"✅ Site added with ID: {data.get('id')}")
            return data
        else:
            print(f"❌ Failed: {response.status_code}")
            return None

    def delete_site(self, site_id):
        """Delete a site"""
        print(f"\n🗑️  Deleting site {site_id}...")

        response = self.session.delete(f"{self.base_url}/api/sites/{site_id}")

        if response.status_code == 200:
            print(f"✅ Site deleted")
            return True
        else:
            print(f"❌ Failed: {response.status_code}")
            return False

    def manual_check(self, site_id):
        """Trigger manual status check"""
        print(f"\n🔄 Triggering check for site {site_id}...")

        response = self.session.post(f"{self.base_url}/api/sites/{site_id}/check")

        if response.status_code == 200:
            print(f"✅ Check triggered")
            return True
        else:
            print(f"❌ Failed: {response.status_code}")
            return False

    # ========================================================================
    # Status & History
    # ========================================================================

    def get_site_history(self, site_id, limit=50):
        """Get status history for a site"""
        print(f"\n📊 Getting history for site {site_id}...")

        response = self.session.get(
            f"{self.base_url}/api/sites/{site_id}/history", params={"limit": limit}
        )

        if response.status_code == 200:
            data = response.json()
            history = data.get("history", [])
            print(f"✅ Got {len(history)} records")

            # Show last 5 entries
            for entry in history[:5]:
                status_icon = "🟢" if entry["status"] == "up" else "🔴"
                time = entry["checked_at"][:16] if entry.get("checked_at") else "?"
                print(f"   {status_icon} {time} - {entry['status']}")

            return data
        else:
            print(f"❌ Failed: {response.status_code}")
            return None

    def get_incidents(self):
        """Get downtime incidents"""
        print("\n🚨 Getting incidents...")

        response = self.session.get(f"{self.base_url}/api/incidents")

        if response.status_code == 200:
            data = response.json()
            incidents = data.get("incidents", [])
            print(f"✅ Found {len(incidents)} incidents")
            return data
        else:
            print(f"❌ Failed: {response.status_code}")
            return None

    # ========================================================================
    # SSL Certificates
    # ========================================================================

    def get_ssl_certificates(self):
        """Get all SSL certificates"""
        print("\n🔒 Getting SSL certificates...")

        response = self.session.get(f"{self.base_url}/api/ssl-certificates")

        if response.status_code == 200:
            data = response.json()
            certs = data.get("certificates", [])
            print(f"✅ Found {len(certs)} certificates:")

            for cert in certs:
                days = cert.get("days_until_expire", 0)
                if days <= 0:
                    icon = "🔴"
                elif days <= 7:
                    icon = "🟠"
                elif days <= 30:
                    icon = "🟡"
                else:
                    icon = "🟢"

                print(f"   {icon} {cert['hostname']} - {days} days left")

            return data
        else:
            print(f"❌ Failed: {response.status_code}")
            return None

    def manual_ssl_check(self):
        """Trigger manual SSL check for all sites"""
        print("\n🔒 Triggering SSL check...")

        response = self.session.post(f"{self.base_url}/api/ssl-certificates/check")

        if response.status_code == 200:
            print(f"✅ SSL check triggered")
            return True
        else:
            print(f"❌ Failed: {response.status_code}")
            return False

    # ========================================================================
    # Statistics
    # ========================================================================

    def get_response_time_stats(self):
        """Get response time statistics"""
        print("\n⏱️  Getting response time stats...")

        response = self.session.get(f"{self.base_url}/api/stats/response-time")

        if response.status_code == 200:
            data = response.json()
            stats = data.get("stats", [])
            print(f"✅ Got stats for {len(stats)} sites:")

            for stat in stats:
                print(
                    f"   {stat['site_name']}: avg={stat['avg_time']:.1f}ms, min={stat['min_time']:.1f}ms, max={stat['max_time']:.1f}ms"
                )

            return data
        else:
            print(f"❌ Failed: {response.status_code}")
            return None

    # ========================================================================
    # Health & System
    # ========================================================================

    def health_check(self):
        """Check API health"""
        print("\n🏥 Checking API health...")

        response = self.session.get(f"{self.base_url}/health")

        if response.status_code == 200:
            data = response.json()
            print(f"✅ Status: {data.get('status')}")
            return data
        else:
            print(f"❌ Failed: {response.status_code}")
            return None


def main():
    """Main demonstration function"""
    print("=" * 60)
    print("Uptime Monitor API Examples")
    print("=" * 60)

    # Initialize client
    client = UptimeMonitorClient()

    # Login
    if not client.login():
        print("Failed to login. Exiting.")
        return

    # Health check
    client.health_check()

    # List sites
    sites = client.list_sites()

    if sites:
        site_id = sites[0]["id"]

        # Get history
        client.get_site_history(site_id, limit=10)

        # Get response time stats
        client.get_response_time_stats()

        # Get SSL certificates
        client.get_ssl_certificates()

        # Get incidents
        client.get_incidents()

    # Add a test site (commented out by default)
    # client.add_site("Test Site", "https://example.com")

    # Manual check
    # if sites:
    #     client.manual_check(sites[0]["id"])

    print("\n" + "=" * 60)
    print("Examples completed!")
    print("=" * 60)


if __name__ == "__main__":
    main()
