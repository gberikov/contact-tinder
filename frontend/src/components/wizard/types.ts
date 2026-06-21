export interface SelectorItem {
  id: string;
  title: string;
  subtitle?: string;
  status?: string;
  statusVariant?: 'default' | 'secondary' | 'destructive' | 'outline' | 'success';
}
