# API Spec

Intro text about the service.

## Responses

Shapes returned by every route.

### Error

All failures return this envelope:

```json
{
  "error": {
    "code": "STRING",
    "message": "STRING"
  }
}
```

### Error Codes

| Code | Meaning |
|------|---------|
| NOT_FOUND | error: the resource does not exist |
| BAD_INPUT | error: validation failed |
| RATE_LIMITED | error: too many requests |

### Success

A bare JSON object per route.

## Auth

Bearer tokens, error responses use the envelope above.
