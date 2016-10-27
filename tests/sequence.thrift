
struct SequenceRequest {
  1: string num
}

struct SequenceResponse {
  1: string num
}

service Sequence {
    SequenceResponse getnum(1: SequenceRequest request),
}

