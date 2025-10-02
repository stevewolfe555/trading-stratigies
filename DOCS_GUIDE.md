# Documentation Guide

**Last Updated**: 2025-10-02

## 📚 Essential Documentation (6 Files)

### Root Level (4 files)

1. **[README.md](README.md)** 📖
   - **Purpose**: Main entry point, getting started
   - **Update**: When features change significantly
   - **Audience**: New users, quick reference

2. **[CURRENT_STATUS.md](CURRENT_STATUS.md)** 🔄
   - **Purpose**: What's working RIGHT NOW
   - **Update**: Frequently (after major changes)
   - **Audience**: Daily reference, troubleshooting

3. **[BACKTESTING_PLAN.md](BACKTESTING_PLAN.md)** 🎯
   - **Purpose**: Next phase roadmap
   - **Update**: When priorities change
   - **Audience**: Planning, next steps

4. **[REFACTORING_COMPLETE.md](REFACTORING_COMPLETE.md)** 📋
   - **Purpose**: Reference document for code refactoring
   - **Update**: Rarely (historical reference)
   - **Audience**: Developers, code review

### docs/ Folder (2 files)

5. **[docs/ARCHITECTURE.md](docs/ARCHITECTURE.md)** 🏗️
   - **Purpose**: System architecture and design
   - **Update**: When structure changes
   - **Audience**: Developers, system understanding

6. **[docs/TIMEZONE_STRATEGY.md](docs/TIMEZONE_STRATEGY.md)** ⏰
   - **Purpose**: Technical decision documentation
   - **Update**: Rarely (stable decision)
   - **Audience**: Developers, timezone handling

## 🎯 Quick Reference

### I want to...

**Get started** → Read [README.md](README.md)

**See what's working** → Read [CURRENT_STATUS.md](CURRENT_STATUS.md)

**Know what's next** → Read [BACKTESTING_PLAN.md](BACKTESTING_PLAN.md)

**Understand the system** → Read [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md)

**Learn about code quality** → Read [REFACTORING_COMPLETE.md](REFACTORING_COMPLETE.md)

**Handle timezones** → Read [docs/TIMEZONE_STRATEGY.md](docs/TIMEZONE_STRATEGY.md)

## ✅ Documentation Principles

1. **Datestamp Everything** - All docs have "Last Updated" at the top
2. **Keep It Current** - Update when things change
3. **Delete Outdated** - Don't keep old docs "just in case"
4. **Single Source of Truth** - No duplicate information
5. **Clear Purpose** - Each doc has one clear purpose

## 📊 What We Removed (10 files)

- `DOCUMENTATION_INDEX.md` - Redundant
- `IMPLEMENTATION_STATUS.md` - Duplicate
- `REFACTORING_SUMMARY.md` - Duplicate
- `docs/SPEC.md` - Outdated
- `docs/IMPLEMENTATION_PLAN.md` - Outdated
- `docs/README.md` - Redundant
- `docs/AUTO_TRADING_SETUP.md` - Info in CURRENT_STATUS
- `docs/PRE_MARKET_CHECKLIST.md` - Not relevant
- `docs/AUCTION_MARKET_GAP_ANALYSIS.md` - Historical
- `docs/MULTI_PROVIDER_SETUP.md` - Info in ARCHITECTURE

**Result**: 13 files → 6 files (54% reduction, 3,158 lines removed)

## 🔄 Update Schedule

### Update Frequently
- `CURRENT_STATUS.md` - After any major feature/fix

### Update Occasionally
- `README.md` - When features change
- `BACKTESTING_PLAN.md` - When priorities shift
- `docs/ARCHITECTURE.md` - When structure changes

### Rarely Update
- `REFACTORING_COMPLETE.md` - Historical reference
- `docs/TIMEZONE_STRATEGY.md` - Stable decision

## 💡 Tips

- **Before adding a new doc**: Check if info fits in existing docs
- **Before updating**: Check the "Last Updated" date
- **After major changes**: Update CURRENT_STATUS.md
- **When confused**: Start with README.md

---

**Remember**: Less documentation is better than outdated documentation! 🎯
