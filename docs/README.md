# Documentation Index

Welcome to the SEM GCP Agents documentation! This directory contains all technical documentation organized by category.

## 📖 Documentation Structure

### 🏗️ Architecture
System design, data models, and technical architecture documentation.

- **[System Overview](architecture/SYSTEM_OVERVIEW.md)** - Complete system architecture, data flow, agent hierarchy, and deployment guide
- **[BigQuery Architecture](architecture/BIGQUERY_ARCHITECTURE.md)** - BigQuery schema design, table structures, and data warehouse patterns
- **[Campaign Taxonomy System](architecture/CAMPAIGN_TAXONOMY_SYSTEM.md)** - Sync groups, campaign classification, and multi-geo management

### 📚 Guides
Step-by-step guides for users and operators.

- **[Getting Started](guides/GETTING_STARTED.md)** - Introduction and first steps
- **[Quick Start](guides/QUICK_START.md)** - Fast setup for development
- **[Deployment Guide](guides/DEPLOYMENT_GUIDE.md)** - Production deployment instructions
- **[Existing Project Setup](guides/EXISTING_PROJECT_SETUP.md)** - Deploy to an existing GCP project (NEW)

### 📋 Reference
Technical reference materials and cheat sheets.

- **[Quick Reference](reference/QUICK_REFERENCE.md)** - Commands, endpoints, and common operations
- **[Gemini SQL Prompts](reference/GEMINI_SQL_PROMPTS.md)** - SQL generation prompts and examples for Gemini

### 🔌 Integrations
Third-party service integrations and setup guides.

- **[Portkey Integration](integrations/PORTKEY_INTEGRATION.md)** - LLM gateway integration overview
- **[Setup Portkey](integrations/SETUP_PORTKEY.md)** - Portkey configuration steps

### 🛠️ Development
Documentation for contributors and developers.

- **[Implementation Status](development/IMPLEMENTATION_STATUS.md)** - Project roadmap and task tracking
- **[Enhancements Summary](development/ENHANCEMENTS_SUMMARY.md)** - Recent improvements and changes
- **[Agent Exclusions Changes](development/AGENT_EXCLUSIONS_CHANGES.md)** - Campaign filtering changes

---

## 🚀 Quick Links

**New to the project?** Start here:
1. [System Overview](architecture/SYSTEM_OVERVIEW.md) - Understand the system
2. [Getting Started](guides/GETTING_STARTED.md) - Set up your environment
3. [Quick Reference](reference/QUICK_REFERENCE.md) - Common commands

**Deploying to production?**
1. [Deployment Guide](guides/DEPLOYMENT_GUIDE.md) - Complete deployment walkthrough
2. [BigQuery Architecture](architecture/BIGQUERY_ARCHITECTURE.md) - Database setup

**Developing agents?**
1. [System Overview](architecture/SYSTEM_OVERVIEW.md) - Agent hierarchy and patterns
2. [Gemini SQL Prompts](reference/GEMINI_SQL_PROMPTS.md) - SQL generation examples
3. [Implementation Status](development/IMPLEMENTATION_STATUS.md) - What's been built

**Working with multi-geo campaigns?**
1. [Campaign Taxonomy System](architecture/CAMPAIGN_TAXONOMY_SYSTEM.md) - Sync groups explained

---

## 📝 Documentation Standards

When adding new documentation:

- **Architecture docs**: High-level system design, data models, technical decisions
- **Guides**: Step-by-step instructions with prerequisites and expected outcomes
- **Reference**: Quick lookups, commands, API specs, examples
- **Integrations**: Third-party service setup and configuration
- **Development**: Project management, roadmaps, changelogs

Keep docs concise, use code examples, and update the index when adding new files.

---

**Last Updated**: 2026-04-15
