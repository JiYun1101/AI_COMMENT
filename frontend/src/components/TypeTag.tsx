import { COMMENT_TYPE_COLOR, COMMENT_TYPE_LABEL, type CommentType } from '../types/comment';

function resolveType(type: string): CommentType {
  return (type in COMMENT_TYPE_LABEL ? type : 'general') as CommentType;
}

interface TypeTagProps {
  type: string;
}

export function TypeTag({ type }: TypeTagProps) {
  const key = resolveType(type);
  const style = COMMENT_TYPE_COLOR[key];
  return (
    <span className="type-tag" style={{ background: style.bg, color: style.fg }}>
      <span className="type-dot" style={{ background: style.dot }} />
      {COMMENT_TYPE_LABEL[key]}
    </span>
  );
}
