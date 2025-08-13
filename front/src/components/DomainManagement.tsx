import React, { useState } from 'react';
import { Table, Button, Modal, Form, Input, Popconfirm, message, Space, Switch } from 'antd';
import { useQuery, useMutation } from '@tanstack/react-query';
import { DomainRead, DomainCreate, DomainUpdate } from '../types/schemas';
import { createDomain, getDomains, updateDomain, deleteDomain } from '../api/domain.api';

const DomainManagement: React.FC = () => {
  const [isModalOpen, setIsModalOpen] = useState(false);
  const [editingDomain, setEditingDomain] = useState<DomainRead | null>(null);
  const [form] = Form.useForm();

  const { data: domains = [], refetch, isLoading } = useQuery<DomainRead[]>({
    queryKey: ['domains'],
    queryFn: getDomains,
  });

  const { mutate: createMutate, isPending: isCreating } = useMutation({
    mutationFn: (payload: DomainCreate) => createDomain(payload),
    onSuccess: () => {
      message.success('Домен створено');
      refetch();
      setIsModalOpen(false);
      form.resetFields();
    },
    onError: (err: any) => message.error(err?.response?.data?.detail || err.message || 'Помилка'),
  });

  const { mutate: updateMutate, isPending: isUpdating } = useMutation({
    mutationFn: ({ name, data }: { name: string; data: DomainUpdate }) => {
      return updateDomain(name, data); // повертаємо Promise
    },
    onSuccess: () => {
      message.success("Домен оновлено");
      refetch();
      setIsModalOpen(false);
      setEditingDomain(null);
      form.resetFields();
    },
    onError: (err: any) =>
      message.error(err?.response?.data?.detail || err.message || "Помилка"),
  });

  const { mutate: deleteMutate, isPending: isDeleting } = useMutation({
    mutationFn: (name: string) => {
      return deleteDomain(name); // повертаємо Promise
    },
    onSuccess: () => {
      message.success("Домен видалено");
      refetch();
    },
    onError: (err: any) =>
      message.error(err?.response?.data?.detail || err.message || "Помилка"),
  });

  const openCreateModal = () => {
    setEditingDomain(null);
    form.resetFields();
    setIsModalOpen(true);
  };

  const openEditModal = (domain: DomainRead) => {
    setEditingDomain(domain);
    form.setFieldsValue({
      name: domain.name,
      description: domain.description,
    });
    setIsModalOpen(true);
  };

  const handleCancel = () => {
    setIsModalOpen(false);
    setEditingDomain(null);
    form.resetFields();
  };

  const onFinish = (values: any) => {
    if (editingDomain) {
      updateMutate({ name: editingDomain.name, data: values });
    } else {
      createMutate(values as DomainCreate);
    }
  };

  const columns = [
    { title: 'ID', dataIndex: 'id', key: 'id', width: 70 },
    { title: 'Домен', dataIndex: 'name', key: 'name' },
    { title: 'Опис', dataIndex: 'description', key: 'description', ellipsis: true },
    { title: 'Активний', dataIndex: 'is_active', key: 'is_active', render: (val: boolean) => (val ? 'Так' : 'Ні') },
    { title: 'Створено', dataIndex: 'created_at', key: 'created_at' },
    {
      title: 'Дії',
      key: 'actions',
      render: (_: any, record: DomainRead) => (
        <Space>
          <Button onClick={() => openEditModal(record)}>Редагувати</Button>
          <Popconfirm
            title="Впевнені, що хочете видалити домен?"
            onConfirm={() => deleteMutate(record.name)}
            okText="Так"
            cancelText="Ні"
          >
            <Button danger loading={isDeleting}>Видалити</Button>
          </Popconfirm>
        </Space>
      ),
    },
  ];

  return (
    <div>
      <Space style={{ marginBottom: 12 }}>
        <Button type="primary" onClick={openCreateModal}>Додати домен</Button>
        <Button onClick={() => refetch()}>Оновити список</Button>
      </Space>

      <Table
        dataSource={domains}
        columns={columns}
        rowKey="name"
        loading={isLoading}
        pagination={{ pageSize: 10 }}
      />

      <Modal
        title={editingDomain ? 'Редагування домену' : 'Новий домен'}
        open={isModalOpen}
        onCancel={handleCancel}
        footer={[
          <Button key="back" onClick={handleCancel}>Відміна</Button>,
          <Button
            key="submit"
            type="primary"
            loading={isCreating || isUpdating}
            onClick={() => form.submit()}
          >
            {editingDomain ? 'Зберегти' : 'Створити'}
          </Button>,
        ]}
      >
        <Form form={form} layout="vertical" onFinish={onFinish} initialValues={{ is_active: true }}>
          <Form.Item name="name" label="Домен" rules={[{ required: true, message: 'Введіть назву домену' }]}>
            <Input />
          </Form.Item>

          <Form.Item name="description" label="Опис">
            <Input.TextArea rows={3} />
          </Form.Item>

          <Form.Item name="is_active" label="Активний" valuePropName="checked">
            <Switch />
          </Form.Item>
        </Form>
      </Modal>
    </div>
  );
};

export default DomainManagement;
