interface Props {
  page: number;
  totalCount: number;
  pageSize: number;
  onPageChange: (page: number) => void;
}

function Pagination({ page, totalCount, pageSize, onPageChange }: Props) {
  const totalPages = Math.ceil(totalCount / pageSize);

  if (totalPages <= 1) return null;

  return (
    <div className="pagination">
      <button disabled={page <= 1} onClick={() => onPageChange(page - 1)}>
        Précédent
      </button>
      <span className="pagination__info">
        Page {page} / {totalPages} ({totalCount.toLocaleString("fr-FR")} jeux)
      </span>
      <button disabled={page >= totalPages} onClick={() => onPageChange(page + 1)}>
        Suivant
      </button>
    </div>
  );
}

export default Pagination;
