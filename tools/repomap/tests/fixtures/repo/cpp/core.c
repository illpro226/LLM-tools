#define MAX_LEN 128

/* A growable byte buffer. */
struct Buffer {
    char *data;
    int len;
};

/* Frees the buffer storage. */
void free_buffer(char *buf)
{
    (void)buf;
}

int run_core(int level)
{
    return level + MAX_LEN;
}
