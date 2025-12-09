# OTS Document JSON Format Specification

## Overview

This document provides a comprehensive specification of the JSON format used for documents in the artdaq-database system. This format is used for both MongoDB storage and filesystem JSON exports.

## Document Structure

```json
{
  "_id": "24-character hex string",
  "collection": "string",
  "version": "string",
  "configtype": "string",
  "changelog": "string",

  "document": {
    "data": { },
    "metadata": { },
    "search": [ ]
  },

  "origin": {
    "source": "string",
    "name": "string",
    "format": "string",
    "created": "ISO 8601 timestamp",
    "rawdata": [ ]
  },

  "bookkeeping": {
    "isdeleted": false,
    "isreadonly": false,
    "created": "ISO 8601 timestamp",
    "updates": [ ]
  },

  "configurations": [ ],
  "entities": [ ],
  "aliases": {
    "active": [ ],
    "history": [ ]
  },
  "runs": [ ],
  "attachments": [ ],
  "comments": [ ]
}
```

---

## Field Reference

### Top-Level Fields

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `_id` | string | Yes | 24-character hexadecimal MongoDB ObjectId |
| `collection` | string | Yes | Collection name (table name, e.g., "GatewaySupervisorTable") |
| `version` | string | Yes | Version number as string (e.g., "1", "42") |
| `configtype` | string | Yes | Configuration type (e.g., "TableConfiguration", "notprovided") |
| `changelog` | string | Yes | Changelog/description text (often "notprovided") |

### _id Field

The document identifier follows MongoDB ObjectId format:
- Exactly 24 hexadecimal characters
- Example: `"6926230499b01f333d06ab75"`
- Generated automatically or can be provided

### collection Field

The collection groups related documents:
- Case-sensitive string
- Typically table names like `"GatewaySupervisorTable"`, `"ARTDAQServicesTable"`
- Used for organizing configuration data

### version Field

Version number within a collection:
- String representation of a number (e.g., `"1"`, `"34"`)
- Unique within a collection (duplicate versions are errors)
- Sequential numbering typically used

---

## document Object

The `document` object contains the actual configuration payload.

```json
{
  "document": {
    "data": {
      "NAME": "GATEWAY_SUPERVISOR_TABLE",
      "COMMENT": "Description text",
      "AUTHOR": "admin",
      "CREATION_TIME": 1764107011,
      "COL_TYPES": {
        "SUPERVISOR_UID": "STRING",
        "PORT": "NUMBER"
      },
      "DATA_SET": [
        {
          "SUPERVISOR_UID": "Supervisor0",
          "PORT": "8080"
        }
      ]
    },
    "metadata": { },
    "search": [ ]
  }
}
```

### document.data

The primary configuration data payload:
- Schema is application-specific
- Typically contains table definitions with:
  - `NAME`: Table identifier
  - `COMMENT`: Description
  - `AUTHOR`: Creator
  - `COL_TYPES`: Column type definitions
  - `DATA_SET`: Array of row data

### document.metadata

Additional metadata about the document:
- Free-form object
- Application-specific usage
- Often empty: `{}`

### document.search

Search index terms:
- Array of searchable values
- Used for full-text search indexing
- Often empty: `[]`

---

## origin Object

Tracks where the document came from.

```json
{
  "origin": {
    "source": "template",
    "name": "notprovided",
    "format": "json",
    "created": "2025-11-25T15:43:31.302-0600",
    "rawdata": []
  }
}
```

| Field | Type | Description |
|-------|------|-------------|
| `source` | string | Origin source: `"template"`, `"import"`, `"user"`, `"migration"` |
| `name` | string | Source identifier or filename |
| `format` | string | Original format: `"json"`, `"fhicl"`, `"xml"` |
| `created` | string | ISO 8601 timestamp when document was created |
| `rawdata` | array | Original raw data (for format conversions) |

---

## bookkeeping Object

Audit trail and document status tracking.

```json
{
  "bookkeeping": {
    "isdeleted": false,
    "isreadonly": false,
    "created": "2025-11-25T15:43:31.302-0600",
    "updates": [
      {
        "event": "addConfiguration",
        "timestamp": "2025-11-25T15:43:31.303-0600",
        "value": {
          "name": "OnlineConfig_v15",
          "assigned": "2025-11-25T15:43:31.303-0600"
        }
      }
    ]
  }
}
```

### Status Fields

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `isdeleted` | boolean | `false` | Soft-delete flag |
| `isreadonly` | boolean | `false` | Prevents further modifications |
| `created` | string | Required | Document creation timestamp |

### updates Array

Array of bookkeeping update events. Each event has:

| Field | Type | Description |
|-------|------|-------------|
| `event` | string | Event type (see Event Types below) |
| `timestamp` | string | ISO 8601 timestamp when event occurred |
| `value` | object | Event-specific data |

### Event Types

| Event | Description | Value Fields |
|-------|-------------|--------------|
| `addConfiguration` | Configuration assigned | `name`, `assigned` |
| `removeConfiguration` | Configuration removed | `name`, `assigned`, `removed` |
| `addAlias` | Alias added | `name`, `assigned` |
| `removeAlias` | Alias removed | `name`, `assigned`, `removed` |
| `addEntity` | Entity assigned | `name`, `assigned` |
| `removeEntity` | Entity removed | `name`, `assigned`, `removed` |
| `addRun` | Run associated | `name`, `assigned` |
| `setVersion` | Version changed | `name`, `assigned` |
| `setCollection` | Collection changed | `name`, `assigned` |
| `setConfigurationType` | Config type changed | `name`, `assigned` |
| `markDeleted` | Document soft-deleted | `deleted: true` |
| `unmarkDeleted` | Document restored | `deleted: false` |
| `markReadOnly` | Document locked | `readonly: true` |
| `unmarkReadOnly` | Document unlocked | `readonly: false` |

---

## configurations Array

List of global configurations that include this document.

```json
{
  "configurations": [
    {
      "name": "OnlineConfiguration_v15",
      "assigned": "2025-11-25T15:43:31.303-0600"
    },
    {
      "name": "MC2ShiftContext_v31",
      "assigned": "2025-11-25T16:00:00.000-0600"
    }
  ]
}
```

| Field | Type | Description |
|-------|------|-------------|
| `name` | string | Configuration name (pattern: `<SystemName>_v<number>`) |
| `assigned` | string | ISO 8601 timestamp when configuration was assigned |

### Configuration Naming Convention

```
<SystemName>_v<VersionNumber>

Examples:
- OnlineConfiguration_v15
- MC2ShiftContext_v31
- ProductionContext_v7
```

---

## entities Array

List of entities (subsystems/components) associated with this document.

```json
{
  "entities": [
    {
      "name": "OTSROOT",
      "assigned": "2025-11-25T15:43:31.303-0600"
    },
    {
      "name": "boardreader01",
      "assigned": "2025-11-25T15:43:31.303-0600"
    }
  ]
}
```

| Field | Type | Description |
|-------|------|-------------|
| `name` | string | Entity name (component/subsystem identifier) |
| `assigned` | string | ISO 8601 timestamp |

### Common Entity Names

- `OTSROOT`: Root/global entity
- `boardreader01`, `boardreader02`: Board reader components
- `dispatcher`: Dispatcher component
- Custom entity names per experiment

---

## aliases Object

Version aliases with active/history tracking.

```json
{
  "aliases": {
    "active": [
      {
        "name": "latest",
        "assigned": "2025-01-15T10:00:00.000-0600"
      },
      {
        "name": "production",
        "assigned": "2025-01-10T08:00:00.000-0600"
      }
    ],
    "history": [
      {
        "name": "testing",
        "assigned": "2024-12-01T09:00:00.000-0600",
        "removed": "2025-01-05T14:30:00.000-0600"
      }
    ]
  }
}
```

### aliases.active

Currently active aliases:

| Field | Type | Description |
|-------|------|-------------|
| `name` | string | Alias name (e.g., "latest", "production") |
| `assigned` | string | ISO 8601 timestamp when alias was assigned |

### aliases.history

Previously removed aliases:

| Field | Type | Description |
|-------|------|-------------|
| `name` | string | Alias name |
| `assigned` | string | Original assignment timestamp |
| `removed` | string | Timestamp when alias was removed |

### Alias Lifecycle

```
1. addAlias → Goes to aliases.active
2. removeAlias → Moves from active to history with removed timestamp
```

---

## runs Array

Data acquisition runs that used this configuration.

```json
{
  "runs": [
    {
      "name": "12345",
      "assigned": "2025-06-01T10:00:00.000-0600"
    },
    {
      "name": "12346",
      "assigned": "2025-06-02T10:00:00.000-0600"
    }
  ]
}
```

| Field | Type | Description |
|-------|------|-------------|
| `name` | string | Run number/identifier |
| `assigned` | string | ISO 8601 timestamp when run was recorded |

---

## attachments Array

File attachments associated with the document.

```json
{
  "attachments": [
    {
      "name": "calibration_data.csv",
      "type": "text/csv",
      "size": 1024,
      "created": "2025-01-15T10:00:00.000-0600"
    }
  ]
}
```

| Field | Type | Description |
|-------|------|-------------|
| `name` | string | Attachment filename |
| `type` | string | MIME type |
| `size` | number | Size in bytes |
| `created` | string | Upload timestamp |

Note: Actual file data may be stored separately or base64-encoded.

---

## comments Array

Source code comments with line references.

```json
{
  "comments": [
    {
      "linenum": 42,
      "text": "This parameter controls the timeout value"
    },
    {
      "linenum": 108,
      "text": "Deprecated: use NEW_PARAM instead"
    }
  ]
}
```

| Field | Type | Description |
|-------|------|-------------|
| `linenum` | integer | Line number reference in source |
| `text` | string | Comment text |

---

## Timestamp Format

All timestamps use ISO 8601 format with timezone offset:

```
YYYY-MM-DDTHH:MM:SS.mmm±HHMM

Examples:
- "2025-11-25T15:43:31.302-0600"
- "2025-01-15T10:00:00.000+0000"
- "2024-12-31T23:59:59.999-0500"
```

### Components

| Part | Format | Description |
|------|--------|-------------|
| Date | `YYYY-MM-DD` | Year-Month-Day |
| Separator | `T` | Date/time separator |
| Time | `HH:MM:SS` | 24-hour time |
| Milliseconds | `.mmm` | 3-digit milliseconds |
| Timezone | `±HHMM` | Offset from UTC (e.g., `-0600` for CST) |

### Legacy Format

Some older documents may contain legacy timestamp format:
```
"Sat Jan 14 02:19:39 2017"
```

The system should handle both formats for backward compatibility.

---

## Complete Document Example

```json
{
  "_id": "6926230499b01f333d06ab75",
  "collection": "GatewaySupervisorTable",
  "version": "34",
  "configtype": "TableConfiguration",
  "changelog": "Updated supervisor settings for production",

  "document": {
    "data": {
      "NAME": "GATEWAY_SUPERVISOR_TABLE",
      "COMMENT": "State Machine group link configuration",
      "AUTHOR": "admin",
      "CREATION_TIME": 1764107011,
      "COL_TYPES": {
        "SUPERVISOR_UID": "STRING",
        "NUMBER_OF_STATE_MACHINE_BROADCAST_THREADS": "NUMBER",
        "LINK_TO_STATE_MACHINE_TABLE": "STRING",
        "STATE_MACHINE_GROUP_ID": "STRING"
      },
      "DATA_SET": [
        {
          "SUPERVISOR_UID": "Supervisor0",
          "NUMBER_OF_STATE_MACHINE_BROADCAST_THREADS": "0",
          "LINK_TO_STATE_MACHINE_TABLE": "StateMachineTable",
          "STATE_MACHINE_GROUP_ID": "Supervisor0_FSMs"
        }
      ]
    },
    "metadata": {},
    "search": []
  },

  "origin": {
    "source": "template",
    "name": "default_gateway_config",
    "format": "json",
    "created": "2025-11-25T15:43:31.302-0600",
    "rawdata": []
  },

  "bookkeeping": {
    "isdeleted": false,
    "isreadonly": false,
    "created": "2025-11-25T15:43:31.302-0600",
    "updates": [
      {
        "event": "setVersion",
        "timestamp": "2025-11-25T15:43:31.303-0600",
        "value": {
          "name": "34",
          "assigned": "2025-11-25T15:43:31.303-0600"
        }
      },
      {
        "event": "setCollection",
        "timestamp": "2025-11-25T15:43:31.303-0600",
        "value": {
          "name": "GatewaySupervisorTable",
          "assigned": "2025-11-25T15:43:31.303-0600"
        }
      },
      {
        "event": "addEntity",
        "timestamp": "2025-11-25T15:43:31.303-0600",
        "value": {
          "name": "OTSROOT",
          "assigned": "2025-11-25T15:43:31.303-0600"
        }
      },
      {
        "event": "addConfiguration",
        "timestamp": "2025-11-25T15:43:32.333-0600",
        "value": {
          "name": "MC2ShiftContext_v31",
          "assigned": "2025-11-25T15:43:32.333-0600"
        }
      }
    ]
  },

  "configurations": [
    {
      "name": "MC2ShiftContext_v31",
      "assigned": "2025-11-25T15:43:32.333-0600"
    }
  ],

  "entities": [
    {
      "name": "OTSROOT",
      "assigned": "2025-11-25T15:43:31.303-0600"
    }
  ],

  "aliases": {
    "active": [
      {
        "name": "production",
        "assigned": "2025-11-25T16:00:00.000-0600"
      }
    ],
    "history": []
  },

  "runs": [
    {
      "name": "12345",
      "assigned": "2025-11-26T10:00:00.000-0600"
    }
  ],

  "attachments": [],
  "comments": []
}
```

---

## Validation Rules

### Required Fields

These fields must always be present:
- `_id` (24-char hex)
- `collection`
- `version`
- `configtype`
- `changelog`
- `document` (with `data`, `metadata`, `search`)
- `origin` (with `source`, `name`, `format`, `created`, `rawdata`)
- `bookkeeping` (with `isdeleted`, `isreadonly`, `created`, `updates`)
- `configurations`
- `entities`
- `aliases` (with `active`, `history`)
- `runs`
- `attachments`
- `comments`

### Default Values

| Field | Default |
|-------|---------|
| `configtype` | `"notprovided"` |
| `changelog` | `"notprovided"` |
| `origin.name` | `"notprovided"` |
| `bookkeeping.isdeleted` | `false` |
| `bookkeeping.isreadonly` | `false` |
| All arrays | `[]` |
| `document.metadata` | `{}` |

### Uniqueness Constraints

| Scope | Unique Field(s) |
|-------|-----------------|
| Database | `_id` |
| Collection | `version` (only one document per version) |
| Configuration | `collection` (only one document per collection in a config) |

