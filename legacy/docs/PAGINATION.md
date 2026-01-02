# Pagination Implementation

## Problem

The Confluence REST API limits the number of results per request:
- **Default limit**: 25 results
- **Maximum limit**: Usually 100-200 (varies by Confluence version/configuration)
- **Previous behavior**: Scripts only fetched first 100-200 results even with `limit=1000`

### What This Meant:
- `confluence-fzf.sh` only showed first ~100 pages
- `confluence-create.sh` only showed first 100 spaces
- Large Confluence instances (>200 pages/spaces) had missing data

## Solution: Automatic Pagination

Both scripts now implement **automatic pagination** that fetches ALL results:

### How It Works

```bash
# 1. Start with empty results
PAGES_JSON=""
START=0
LIMIT=100  # Request 100 per page

# 2. Loop until no more results
while true; do
    # Fetch one page of results
    PAGE_JSON=$(curl -s -u "$USERNAME:$PASSWORD" \
        "$BASE_URL/rest/api/content?type=page&limit=$LIMIT&start=$START&expand=space")

    # If empty response, we're done
    if [[ -z "$PAGE_JSON" ]]; then
        break
    fi

    # Merge with previous results
    if [[ -z "$PAGES_JSON" ]]; then
        PAGES_JSON="$PAGE_JSON"
    else
        # Combine results arrays using Python
        PAGES_JSON=$(echo "$PAGES_JSON" "$PAGE_JSON" | python3 -c '
import json, sys
lines = sys.stdin.read().strip().split("\\n")
data1 = json.loads(lines[0])
data2 = json.loads(lines[1])
data1["results"].extend(data2.get("results", []))
print(json.dumps(data1))
')
    fi

    # Check if this was the last page
    PAGE_SIZE=$(echo "$PAGE_JSON" | python3 -c 'import json,sys; print(len(json.load(sys.stdin).get("results", [])))')
    if [[ $PAGE_SIZE -lt $LIMIT ]]; then
        break  # Got fewer results than requested = last page
    fi

    # Move to next page
    START=$((START + LIMIT))
    echo "  Fetched $START items so far..."
done
```

### Key Changes

#### confluence-fzf.sh
**Before:**
```bash
PAGES_JSON=$(curl -s -u "$USERNAME:$PASSWORD" \
    "$BASE_URL/rest/api/content?type=page&limit=1000&expand=space")
```
- Only fetched first ~100-200 pages

**After:**
- Pagination loop fetches ALL pages
- Progress indicator: "Fetched 100 pages so far..."
- Complete dataset for large instances

#### confluence-create.sh
**Spaces (Before):**
```bash
SPACES_JSON=$(curl -s -u "$USERNAME:$PASSWORD" \
    "$BASE_URL/rest/api/space?limit=100")
```
- Only fetched first 100 spaces

**Spaces (After):**
- Pagination loop fetches ALL spaces

**Parent Pages (Before):**
```bash
PAGES_JSON=$(curl -s -u "$USERNAME:$PASSWORD" \
    "$BASE_URL/rest/api/content?type=page&spaceKey=$SPACE_KEY&limit=1000")
```
- Only fetched first ~100-200 pages per space

**Parent Pages (After):**
- Pagination loop fetches ALL pages in the space

## Performance Considerations

### API Calls
- **Small instances (<100 items)**: 1 API call (same as before)
- **Medium instances (100-500 items)**: 2-5 API calls
- **Large instances (>1000 items)**: 10+ API calls

### User Experience
- Progress indicators show fetch status
- Slight delay for large instances (few seconds)
- Complete data visibility

### Example Output

```bash
Fetching pages from http://confluence.example.com... (fzf mode)
  Fetched 100 pages so far...
  Fetched 200 pages so far...
  Fetched 300 pages so far...
Found 347 pages
```

## Technical Details

### Pagination Parameters

- **`start`**: Offset for results (0-indexed)
- **`limit`**: Number of results per page (max 100-200)

### API Response Structure

```json
{
  "results": [...],    // Array of pages/spaces
  "start": 0,          // Starting index
  "limit": 100,        // Requested limit
  "size": 100,         // Actual results returned
  "_links": {
    "next": "..."      // Link to next page (if exists)
  }
}
```

### Detection Logic

We detect the last page when:
1. Response is empty (no JSON)
2. `size < limit` (fewer results than requested)

## Benefits

✅ **Complete data access** - All spaces and pages visible
✅ **Scalable** - Works with instances of any size
✅ **Backward compatible** - No breaking changes to usage
✅ **Progress feedback** - User knows when large fetches are happening
✅ **Efficient** - Only makes necessary API calls

## Limitations

⚠️ **Large instances**: First load may take a few seconds
⚠️ **API rate limiting**: Very large instances (10k+ pages) might hit rate limits
⚠️ **Memory usage**: All results stored in memory (typically fine for <10k items)

## Alternative: Add Filtering

For very large instances, consider adding filtering options:

```bash
# Future enhancement ideas
./confluence-fzf.sh --space MYSPACE     # Only show pages from one space
./confluence-fzf.sh --recent 30         # Only show pages modified in last 30 days
./confluence-fzf.sh --max-results 500   # Limit total results
```

## Testing

To verify pagination is working:

```bash
# Check how many total pages are fetched
./confluence-fzf.sh 2>&1 | grep "Found .* pages"

# Watch pagination in action
./confluence-fzf.sh 2>&1 | grep "Fetched"

# Should see output like:
#   Fetched 100 pages so far...
#   Fetched 200 pages so far...
#   Found 237 pages
```

## Confluence API Limits

Different Confluence versions/configurations may have different limits:

| Confluence Version | Default Limit | Max Limit |
|-------------------|---------------|-----------|
| Server/DC 6.x     | 25            | 100       |
| Server/DC 7.x     | 25            | 200       |
| Cloud             | 25            | 250       |

Our implementation uses `limit=100` which works across all versions while being efficient.
