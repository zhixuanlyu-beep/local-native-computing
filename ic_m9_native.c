/* Optional packed executor for the M7 FIFO port-graph schedule.  The caller
 * supplies M7's ordered rules and the initial GraphSpec's ordered wires. */
#include <stdlib.h>
#include <string.h>

#ifdef _WIN32
#define EXPORT __declspec(dllexport)
#else
#define EXPORT
#endif

enum { GAMMA, DELTA, EPSILON };
enum { RULE_COUNT = 6, RULE_WIDTH = 24, LOCAL_PORTS = 20 };

typedef struct {
    int status, steps, peak, cycles, cell_count, live, census[RULE_COUNT];
    int *kinds, *adj;
} Result;

typedef struct {
    Result *result;
    int cell_capacity;
    int *queue;
    int head, tail, queue_capacity;
} Net;

typedef struct {
    int neighbor[LOCAL_PORTS][2], degree[LOCAL_PORTS];
    int insertion[LOCAL_PORTS], length;
} Splice;

static int principal(int cell) { return 1 + 3 * cell; }
static int cell_of(int port) { return (port - 1) / 3; }
static int arity(int kind) { return kind == EPSILON ? 0 : 2; }

static int grow(void *old, int count, int width, int **result) {
    int *memory = realloc(old, (size_t)count * width * sizeof(int));
    if (!memory) return 0;
    *result = memory;
    return 1;
}

static int reserve_cells(Net *net, int needed) {
    Result *r = net->result;
    if (needed <= net->cell_capacity) return 1;
    int capacity = net->cell_capacity ? 2 * net->cell_capacity : 64;
    if (capacity < needed) capacity = needed;
    if (!grow(r->kinds, capacity, 1, &r->kinds)
            || !grow(r->adj, capacity + 1, 3, &r->adj)) return 0;
    net->cell_capacity = capacity;
    return 1;
}

static int add_cell(Net *net, int kind) {
    Result *r = net->result;
    int cell = r->cell_count;
    if (!reserve_cells(net, cell + 1)) return -1;
    r->kinds[cell] = kind;
    for (int p = principal(cell); p < principal(cell) + 3; p++) r->adj[p] = -1;
    r->cell_count++;
    r->live++;
    return cell;
}

static int link_ports(Net *net, int a, int b) {
    Result *r = net->result;
    if (a == b || r->adj[a] != -1 || r->adj[b] != -1) return 0;
    r->adj[a] = b;
    r->adj[b] = a;
    if (a % 3 == 1 && b % 3 == 1) {
        if (net->tail == net->queue_capacity) {
            int capacity = net->queue_capacity ? 2 * net->queue_capacity : 64;
            if (!grow(net->queue, capacity, 1, &net->queue)) return 0;
            net->queue_capacity = capacity;
        }
        net->queue[net->tail++] = a;
    }
    return 1;
}

/* M7 starts each redex with the lexicographically smaller c<number> name. */
static int lexical_after(int a, int b) {
    int highest_a = 1, highest_b = 1;
    while (a / highest_a >= 10) highest_a *= 10;
    while (b / highest_b >= 10) highest_b *= 10;
    while (highest_a && highest_b) {
        int digit_a = a / highest_a, digit_b = b / highest_b;
        if (digit_a != digit_b) return digit_a > digit_b;
        a %= highest_a;
        b %= highest_b;
        highest_a /= 10;
        highest_b /= 10;
    }
    return highest_a != 0;
}

static int put_edge(Splice *splice, int a, int b) {
    if (a < 0 || a >= LOCAL_PORTS || b < 0 || b >= LOCAL_PORTS || a == b
            || splice->degree[a] == 2 || splice->degree[b] == 2) return 0;
    if (!splice->degree[a]) splice->insertion[splice->length++] = a;
    splice->neighbor[a][splice->degree[a]++] = b;
    if (!splice->degree[b]) splice->insertion[splice->length++] = b;
    splice->neighbor[b][splice->degree[b]++] = a;
    return 1;
}

static int apply_rule(Net *net, int a, int b, const int *rules) {
    Result *r = net->result;
    if (lexical_after(a, b)) { int old_a = a; a = b; b = old_a; }
    int rule_index;
    const int *rule = rules;
    for (rule_index = 0; rule_index < RULE_COUNT; rule_index++, rule += RULE_WIDTH) {
        if (rule[0] == r->kinds[a] && rule[1] == r->kinds[b]) break;
        if (rule[0] == r->kinds[b] && rule[1] == r->kinds[a]) {
            int old_a = a; a = b; b = old_a;
            break;
        }
    }
    if (rule_index == RULE_COUNT) return 0;
    int sides[] = {a, b};
    int connector[] = {-1, -1, -1, -1};
    for (int side = 0; side < 2; side++) {
        if (arity(r->kinds[sides[side]])) {
            connector[2 * side] = principal(sides[side]) + 1;
            connector[2 * side + 1] = principal(sides[side]) + 2;
        }
    }
    Splice splice = {0};
    int terminals[LOCAL_PORTS];
    for (int i = 0; i < LOCAL_PORTS; i++) terminals[i] = -1;
    for (int slot = 0; slot < 4; slot++) {
        if (connector[slot] < 0) continue;
        int peer = r->adj[connector[slot]], internal = 0;
        for (int other = 0; other < 4; other++) {
            if (connector[other] != peer) continue;
            if (slot < other && !put_edge(&splice, slot, other)) return 0;
            internal = 1;
            break;
        }
        if (!internal) {
            terminals[16 + slot] = peer;
            if (peer < 0 || !put_edge(&splice, slot, 16 + slot)) return 0;
        }
    }
    for (int cell = 0; cell < rule[2]; cell++) {
        int created = add_cell(net, rule[4 + cell]);
        if (created < 0) return 0;
        for (int port = 0; port <= arity(rule[4 + cell]); port++)
            terminals[4 + 3 * cell + port] = principal(created) + port;
    }
    for (int wire = 0; wire < rule[3]; wire++)
        if (!put_edge(&splice, rule[8 + 2 * wire], rule[9 + 2 * wire])) return 0;

    for (int side = 0; side < 2; side++) {
        int cell = sides[side];
        for (int p = principal(cell); p <= principal(cell) + arity(r->kinds[cell]); p++) {
            if (r->adj[p] >= 0) r->adj[r->adj[p]] = -1;
            r->adj[p] = -1;
        }
        r->kinds[cell] = -1;
    }
    r->live -= 2;

    int visited[LOCAL_PORTS] = {0};
    for (int i = 0; i < splice.length; i++) {
        int start = splice.insertion[i];
        if (visited[start]) continue;
        int pending[LOCAL_PORTS], remaining = 0, ends[2], count = 0;
        pending[remaining++] = start;
        visited[start] = 1;
        while (remaining) {
            int node = pending[--remaining];
            if (node >= 4) {
                if (count == 2 || terminals[node] < 0) return 0;
                ends[count++] = terminals[node];
            }
            for (int j = 0; j < splice.degree[node]; j++) {
                int other = splice.neighbor[node][j];
                if (!visited[other]) {
                    visited[other] = 1;
                    pending[remaining++] = other;
                }
            }
        }
        if (count == 0) r->cycles++;
        else if (count != 2 || !link_ports(net, ends[0], ends[1])) return 0;
    }
    r->census[rule_index]++;
    return 1;
}

EXPORT void m9_free(Result *out) {
    free(out->kinds);
    free(out->adj);
    out->kinds = NULL;
    out->adj = NULL;
}

EXPORT int m9_run(int n, const int *kinds, int edge_count, const int *edges,
                  const int *rules, int initial_cycles, int max_steps,
                  int max_cells, Result *out) {
    memset(out, 0, sizeof(*out));
    Net net = {0};
    net.result = out;
    if (!reserve_cells(&net, n + 1)) goto fail;
    out->adj[0] = -1;
    for (int i = 0; i < n; i++) if (add_cell(&net, kinds[i]) < 0) goto fail;
    for (int i = 0; i < edge_count; i++)
        if (!link_ports(&net, edges[2 * i], edges[2 * i + 1])) goto fail;
    out->cycles = initial_cycles;
    out->peak = n;
    while (1) {
        if (out->live > max_cells) { out->status = 2; break; }
        if (net.head == net.tail) break;
        if (out->steps >= max_steps) { out->status = 1; break; }
        int port = net.queue[net.head++];
        int peer = out->adj[port];
        if (peer < 0 || peer % 3 != 1 || !apply_rule(&net, cell_of(port), cell_of(peer), rules)) goto fail;
        out->steps++;
        if (out->live > out->peak) out->peak = out->live;
    }
    free(net.queue);
    return 0;
fail:
    free(net.queue);
    m9_free(out);
    return -1;
}
