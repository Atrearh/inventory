// src/hooks/useModalForm.ts
import { useState, useCallback } from "react";
import { FormInstance } from "antd";

// Інтерфейс для типізації хука
interface UseModalFormProps<T> {
  form: FormInstance;
  defaultValues?: Partial<T>;
}

interface UseModalFormResult<T> {
  isModalOpen: boolean;
  editingItem: T | null;
  openCreateModal: () => void;
  openEditModal: (item: T) => void;
  handleCancel: () => void;
}

export function useModalForm<T>({
  form,
  defaultValues,
}: UseModalFormProps<T>): UseModalFormResult<T> {
  const [isModalOpen, setIsModalOpen] = useState(false);
  const [editingItem, setEditingItem] = useState<T | null>(null);

  // Відкриття модального вікна для створення
  const openCreateModal = useCallback(() => {
    setEditingItem(null);
    form.resetFields();
    if (defaultValues) {
      form.setFieldsValue(defaultValues);
    }
    setIsModalOpen(true);
  }, [form, defaultValues]);

  // Відкриття модального вікна для редагування
  const openEditModal = useCallback(
    (item: T) => {
      setEditingItem(item);
      form.setFieldsValue(item);
      setIsModalOpen(true);
    },
    [form],
  );

  // Закриття модального вікна
  const handleCancel = useCallback(() => {
    setIsModalOpen(false);
    setEditingItem(null);
    form.resetFields();
  }, [form]);

  return {
    isModalOpen,
    editingItem,
    openCreateModal,
    openEditModal,
    handleCancel,
  };
}
