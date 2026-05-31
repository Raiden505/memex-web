interface DateDividerProps {
  label: string;
}

export default function DateDivider({ label }: DateDividerProps) {
  return (
    <div className="flex justify-center my-8">
      <span className="font-label-md text-label-md text-outline py-1 px-4 rounded-full border border-outline-variant/30 bg-surface-container-low uppercase tracking-wider">
        {label}
      </span>
    </div>
  );
}
